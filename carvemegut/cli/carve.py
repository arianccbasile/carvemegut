from carvemegut import config, project_dir
from carvemegut import __version__ as version
from carvemegut.reconstruction.carving import carve_model, build_ensemble
from carvemegut.reconstruction.eggnog import load_eggnog_data
from carvemegut.reconstruction.gapfilling import multiGapFill
from carvemegut.reconstruction.utils import load_media_db, load_soft_constraints, load_hard_constraints, annotate_genes
from carvemegut.reconstruction.ncbi_download import load_ncbi_table, download_ncbi_genome
from carvemegut.reconstruction.scoring import reaction_scoring
from carvemegut.reconstruction.diamond import run_blast, load_diamond_results
from reframed.cobra.ensemble import save_ensemble
from reframed import load_cbmodel, save_cbmodel, Environment
from reframed.io.sbml import sanitize_id
import argparse
import os
import os.path
import pandas as pd
from multiprocessing import Pool
from glob import glob
import subprocess
from Bio import SeqIO
import uuid

def first_run_check():
    diamond_db = project_dir + config.get('generated', 'diamond_db')
    if not os.path.exists(diamond_db):
        print("Running diamond for the first time, please wait while we build the internal database...")
        fasta_file = project_dir + config.get('generated', 'fasta_file')
        cmd = ['diamond', 'makedb', '--in', fasta_file, '-d', diamond_db[:-5]]
        try:
            exit_code = subprocess.call(cmd)
        except OSError:
            print('Unable to run diamond (make sure diamond is available in your PATH).')
        else:
            if exit_code != 0:
                print('Failed to run diamond (wrong arguments).')

def concatenate_multifasta(input_files, output_file):
    with open(output_file, 'w') as out_file:
        for file_name in input_files:
            with open(file_name, 'r') as in_file:
                for line in in_file:
                    out_file.write(line)

def concatenate_files_by_value(agora_prot_folder,file, taxonomic_level, label,output):
    # Filter the dataframe to get entries that match the specified value in the given column
    df=pd.read_csv(file,sep="\t",header=0)
    taxonomic_level = ''.join([char.capitalize() if i == 0 else char.lower() for i, char in enumerate(taxonomic_level)])
    label = ''.join([char.capitalize() if i == 0 else char.lower() for i, char in enumerate(label)])
    filtered_entries = df[df[taxonomic_level] == label]

    # Assuming the column containing filenames is named 'file_name'
    file_names = filtered_entries['MicrobeID'].tolist()
    
    selected_sequences={}

    # Iterate through file names and concatenate files with the same name as entries
    for file_prot in file_names:
        if os.path.exists(agora_prot_folder+file_prot+".faa"):
            with open(agora_prot_folder+file_prot+".faa","r") as handle:
                for record in SeqIO.parse(handle, "fasta"):
                    selected_sequences[record.id]=str(record.seq)
    with open(output,"w") as out_w:
        for ele in selected_sequences.keys():
            out_w.write(">"+ele+"\n"+selected_sequences[ele]+"\n")


def build_model_id(name):
    model_id = sanitize_id(name)
    if not model_id[0].isalpha():
        model_id = 'm_' + model_id
    return model_id


def maincall(inputfile, input_type='protein', outputfile=None, diamond_args=None, universe=None, universe_file=None,
         ensemble_size=None, verbose=False, debug=False, flavor=None, gapfill=None, blind_gapfill=False, init=None,
         mediadb=None, default_score=None, uptake_score=None, soft_score=None, soft=None, hard=None, reference=None,
         ref_score=None, recursive_mode=False,tax_level=None,taxonomy=None):
    
    if tax_level and taxonomy:
        # Generate a random file name for the 'agora_fasta_file'
        random_file_name = project_dir+"data/generated/"+uuid.uuid4().hex + '.fasta'
        agora_fasta_file=random_file_name
        taxonomy_agora = project_dir + config.get('generated', 'taxonomy_agora')
        agora_prot_folder = project_dir + config.get('generated', 'agora_prot_folder')
        
        # Use the newly generated file name
        concatenate_files_by_value(agora_prot_folder, taxonomy_agora, tax_level, taxonomy, agora_fasta_file)
        dedicated_diamond_db= random_file_name[:-5]+"dmnd"
        cmd = ['diamond', 'makedb', '--in', agora_fasta_file, '-d', dedicated_diamond_db[:-5]]
        
        try:
            exit_code = subprocess.call(cmd)
        except OSError:
            print('Unable to run diamond (make sure diamond is available in your PATH).')
        else:
            if exit_code != 0:
                print('Failed to run diamond (wrong arguments).')

    agora_fasta_file = project_dir + config.get('generated', 'agora_fasta_file')
    bigg_fasta_file = project_dir + config.get('generated', 'bigg_fasta_file')
    gapseq_fasta_file = project_dir + config.get('generated', 'gapseq_fasta_file')
    input_files = [bigg_fasta_file, agora_fasta_file, gapseq_fasta_file]
    fasta_file = project_dir + config.get('generated', 'fasta_file')
    output_file = fasta_file 
    concatenate_multifasta(input_files, output_file)
    if recursive_mode:
        model_id = os.path.splitext(os.path.basename(inputfile))[0]

        if outputfile:
            outputfile = f'{outputfile}/{model_id}.xml'
        else:
            outputfile = os.path.splitext(inputfile)[0] + '.xml'

    else:
        if outputfile:
            model_id = os.path.splitext(os.path.basename(outputfile))[0]
        else:
            model_id = os.path.splitext(os.path.basename(inputfile))[0]
            outputfile = os.path.splitext(inputfile)[0] + '.xml'

    model_id = build_model_id(model_id)

    outputfolder = os.path.abspath(os.path.dirname(outputfile))

    if not os.path.exists(outputfolder):
        try:
            os.makedirs(outputfolder)
        except:
            print('Unable to create output folder:', outputfolder)
            return

    if soft:
        try:
            soft_constraints = load_soft_constraints(soft)
        except IOError:
            raise IOError('Failed to load soft-constraints file:' + soft)
    else:
        soft_constraints = None

    if hard:
        try:
            hard_constraints = load_hard_constraints(hard)
        except IOError:
            raise IOError('Failed to load hard-constraints file:' + hard)
    else:
        hard_constraints = None

    if input_type == 'refseq':

        if verbose:
            print(f'Downloading genome {inputfile} from NCBI...')

        ncbi_table = load_ncbi_table(project_dir + config.get('input', 'refseq'))
        inputfile = download_ncbi_genome(inputfile, ncbi_table)

        if not inputfile:
            print('Failed to download genome from NCBI.')
            return

        input_type = 'protein' if inputfile.endswith('.faa.gz') else 'dna'

    if input_type == 'protein' or input_type == 'dna':
        if verbose:
            print('Running diamond...')
        diamond_db = project_dir + config.get('generated', 'diamond_db')
        if taxonomy and tax_level:
            #diamond_db = project_dir + config.get('generated', 'dedicated_diamond_db')
            diamond_db=dedicated_diamond_db
        blast_output = os.path.splitext(inputfile)[0] + '.tsv'
        exit_code = run_blast(inputfile, input_type, blast_output, diamond_db, diamond_args, verbose)

        if exit_code is None:
            print('Unable to run diamond (make sure diamond is available in your PATH).')
            return

        if exit_code != 0:
            print('Failed to run diamond.')
            if diamond_args is not None:
                print('Incorrect diamond args? Please check documentation or use default args.')
            return

        annotations = load_diamond_results(blast_output)
    elif input_type == 'eggnog':
        annotations = load_eggnog_data(inputfile)
    elif input_type == 'diamond':
        annotations = load_diamond_results(inputfile)
    else:
        raise ValueError('Invalid input type: ' + input_type)

    if verbose:
        print('Loading universe model...')

    if not universe_file:
        if universe:
            universe_file = f"{project_dir}{config.get('generated', 'folder')}universe_{universe}.xml.gz"
        else:
            universe_file = project_dir + config.get('generated', 'default_universe')

    try:
        universe_model = load_cbmodel(universe_file, flavor='bigg')
        universe_model.id = model_id
    except IOError:
        available = '\n'.join(glob(f"{project_dir}{config.get('generated', 'folder')}universe_*.xml.gz"))
        raise IOError(f'Failed to load universe model: {universe_file}\nAvailable universe files:\n{available}')

    if reference:
        if verbose:
            print('Loading reference model...')

        try:
            ref_model = load_cbmodel(reference)
        except:
            raise IOError('Failed to load reference model.')
    else:
        ref_model = None

    if gapfill or init:

        if verbose:
            print('Loading media library...')

        if not mediadb:
            mediadb = project_dir + config.get('input', 'media_library')

        try:
            media_db = load_media_db(mediadb)
        except IOError:
            raise IOError('Failed to load media library:' + mediadb)

    if verbose:
        print('Scoring reactions...')

    gene_annotations = pd.read_csv(project_dir + config.get('generated', 'gene_annotations'), sep='\t')
    bigg_gprs = project_dir + config.get('generated', 'bigg_gprs')
    gprs = pd.read_csv(bigg_gprs)
    gprs = gprs[gprs.reaction.isin(universe_model.reactions)]

    debug_output = model_id if debug else None
    scores, gene2gene = reaction_scoring(annotations, gprs, debug_output=debug_output)

    if scores is None:
        print('The input genome did not match sufficient genes/reactions in the database.')
        return

    if not flavor:
        flavor = config.get('sbml', 'default_flavor')

    init_env = None

    if init:
        if init in media_db:
            init_env = Environment.from_compounds(media_db[init])
        else:
            print(f'Error: medium {init} not in media database.')

    universe_model.metadata['Description'] = 'This model was built with CarveMe version ' + version

    if ensemble_size is None or ensemble_size <= 1:
        if verbose:
            print('Reconstructing a single model')

        model = carve_model(universe_model, scores, inplace=(not gapfill), default_score=default_score,
                            uptake_score=uptake_score, soft_score=soft_score, soft_constraints=soft_constraints,
                            hard_constraints=hard_constraints, ref_model=ref_model, ref_score=ref_score,
                            init_env=init_env, debug_output=debug_output,tax_level=tax_level,taxonomy=taxonomy)
        annotate_genes(model, gene2gene, gene_annotations)

    else:
        if verbose:
            print('Building an ensemble of', ensemble_size, 'models')

        ensemble = build_ensemble(universe_model, scores, ensemble_size, init_env=init_env)

        annotate_genes(ensemble.model, gene2gene, gene_annotations)
        save_ensemble(ensemble, outputfile, flavor=flavor)
        return

    if model is None:
        print("Failed to build model.")
        return

    if not gapfill:
        save_cbmodel(model, outputfile, flavor=flavor)

    else:
        media = gapfill.split(',')

        if verbose:
            m1, n1 = len(model.metabolites), len(model.reactions)
            print(f"Gap filling for {', '.join(media)}...")

        max_uptake = config.getint('gapfill', 'max_uptake')

        if blind_gapfill:
            scores = None
        else:
            scores = dict(scores[['reaction', 'normalized_score']].values)
        multiGapFill(model, universe_model, media, media_db, scores=scores, max_uptake=max_uptake, inplace=True)

        if verbose:
            m2, n2 = len(model.metabolites), len(model.reactions)
            print(f'Added {(n2 - n1)} reactions and {(m2 - m1)} metabolites')

        if init_env:  # Initializes environment again as new exchange reactions can be acquired during gap-filling
            init_env.apply(model, inplace=True, warning=False)

        save_cbmodel(model, outputfile, flavor=flavor)

    if taxonomy:
        os.remove(dedicated_diamond_db)
        os.remove(dedicated_diamond_db[:-4]+"fasta")

    if verbose:
        print('Done.')




def main():

    parser = argparse.ArgumentParser(description="Reconstruct a metabolic model using CarveMe",
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('input', metavar='INPUT', nargs='+',
                        help="Input (protein fasta file by default, see other options for details).\n" +
                             "When used with -r an input pattern with wildcards can also be used.\n" +
                             "When used with --refseq an NCBI RefSeq assembly accession is expected."
                        )

    input_type_args = parser.add_mutually_exclusive_group()
    input_type_args.add_argument('--dna', action='store_true', help="Build from DNA fasta file")
    input_type_args.add_argument('--egg', action='store_true', help="Build from eggNOG-mapper output file")
    input_type_args.add_argument('--diamond', action='store_true', help=argparse.SUPPRESS)
    input_type_args.add_argument('--refseq', action='store_true', help="Download genome from NCBI RefSeq and build")

    parser.add_argument('--diamond-args', help="Additional arguments for running diamond")

    parser.add_argument('-r', '--recursive', action='store_true', dest='recursive',
                        help="Bulk reconstruction from folder with genome files")

    parser.add_argument('-o', '--output', dest='output', help="SBML output file (or output folder if -r is used)")

    univ = parser.add_mutually_exclusive_group()
    univ.add_argument('-u', '--universe', dest='universe', help="Pre-built universe model (default: bacteria)")
    univ.add_argument('--universe-file', dest='universe_file', help="Reaction universe file (SBML format)")
    sbml = parser.add_mutually_exclusive_group()
    sbml.add_argument('--cobra', action='store_true', help="Output SBML in old cobra format")
    sbml.add_argument('--fbc2', action='store_true', help="Output SBML in sbml-fbc2 format")

    parser.add_argument('-n', '--ensemble', type=int, dest='ensemble',
                        help="Build model ensemble with N models")
    parser.add_argument('-tl', '--taxonomic_level', dest='tax_level', help="Lowest known taxonomical range (default: None), to be used with -t")
    parser.add_argument('-t', '--taxonomy', dest='taxonomy', help="Taxonomy (default: not specified), to be used with -tl")

    parser.add_argument('-g', '--gapfill', dest='gapfill',
                        help="Gap fill model for given media")

    parser.add_argument('-i', '--init', dest='init',
                        help="Initialize model with given medium")

    parser.add_argument('--mediadb', help="Media database file")

    parser.add_argument('-v', '--verbose', action='store_true', dest='verbose', help="Switch to verbose mode")
    parser.add_argument('-d', '--debug', action='store_true', dest='debug',
                        help="Debug mode: writes intermediate results into output files")

    parser.add_argument('--soft', help="Soft constraints file")
    parser.add_argument('--hard', help="Hard constraints file")

    parser.add_argument('--reference', help="Manually curated model of a close reference species.")

    parser.add_argument('--default-score', type=float, default=-1.0, help=argparse.SUPPRESS)
    parser.add_argument('--uptake-score', type=float, default=0.0, help=argparse.SUPPRESS)
    parser.add_argument('--soft-score', type=float, default=1.0, help=argparse.SUPPRESS)
    parser.add_argument('--reference-score', type=float, default=0.0, help=argparse.SUPPRESS)

    parser.add_argument('--blind-gapfill', action='store_true', help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.gapfill and args.ensemble:
        parser.error('Gap fill and ensemble generation cannot currently be combined (not implemented yet).')

    if (args.soft or args.hard) and args.ensemble:
        parser.error('Soft/hard constraints and ensemble generation cannot currently be combined (not implemented yet).')

    if args.mediadb and not args.gapfill:
        parser.error('--mediadb can only be used with --gapfill')

    if args.recursive and args.refseq:
        parser.error('-r cannot be combined with --refseq')

    if args.egg:
        input_type = 'eggnog'
    elif args.dna:
        input_type = 'dna'
    elif args.diamond:
        input_type = 'diamond'
    elif args.refseq:
        input_type = 'refseq'
    else:
        input_type = 'protein'

    if args.fbc2:
        flavor = 'fbc2'
    elif args.cobra:
        flavor = 'cobra'
    else:
        flavor = config.get('sbml', 'default_flavor')

    first_run_check()

    if not args.recursive:
        if len(args.input) > 1:
            parser.error('Use -r when specifying more than one input file')

        maincall(
            inputfile=args.input[0],
            input_type=input_type,
            outputfile=args.output,
            diamond_args=args.diamond_args,
            universe=args.universe,
            universe_file=args.universe_file,
            ensemble_size=args.ensemble,
            verbose=args.verbose,
            debug=args.debug,
            flavor=flavor,
            gapfill=args.gapfill,
            blind_gapfill=False,
            init=args.init,
            mediadb=args.mediadb,
            default_score=args.default_score,
            uptake_score=args.uptake_score,
            soft_score=args.soft_score,
            soft=args.soft,
            hard=args.hard,
            reference=args.reference,
            ref_score=args.reference_score,
            taxonomy=args.taxonomy,
            tax_level=args.tax_level
        )

    else:

        def f(x):
            maincall(
                inputfile=x,
                input_type=input_type,
                outputfile=args.output,
                diamond_args=args.diamond_args,
                universe=args.universe,
                universe_file=args.universe_file,
                ensemble_size=args.ensemble,
                verbose=args.verbose,
                flavor=flavor,
                gapfill=args.gapfill,
                blind_gapfill=False,
                init=args.init,
                mediadb=args.mediadb,
                default_score=args.default_score,
                uptake_score=args.uptake_score,
                soft_score=args.soft_score,
                soft=args.soft,
                hard=args.hard,
                reference=args.reference,
                ref_score=args.reference_score,
                recursive_mode=True,
                taxonomy=args.taxonomy,
                tax_level=args.tax_level
            )

        p = Pool()
        p.map(f, args.input)


if __name__ == '__main__':
    main()
