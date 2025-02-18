import os
import sys
import site

def fix_path():
    """Ensure user's bin directory is in the PATH."""
    user_bin = os.path.expanduser("~/.local/bin")

    if user_bin not in os.environ["PATH"]:
        os.environ["PATH"] += os.pathsep + user_bin
        print(f"Updated PATH: {os.environ['PATH']}")

        # Aggiorna il profilo della shell per renderlo persistente
        shell_config = os.path.expanduser("~/.bashrc")  # Per Linux/macOS
        if not os.path.exists(shell_config):
            shell_config = os.path.expanduser("~/.bash_profile")

        with open(shell_config, "a") as f:
            f.write(f"\nexport PATH={user_bin}:$PATH\n")

        print("Added ~/.local/bin to PATH. Restart your shell or run `source ~/.bashrc`.")

if __name__ == "__main__":
    fix_path()

