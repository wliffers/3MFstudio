"""Pruefwerkzeuge des 3MF-Konsortiums nach conformance/ holen - nur fuer Tests, nie ins Paket.

- conformance/test_suites: die offiziellen Konformitaetstests (BSD-2-Clause), nur die Gruppen, die 3MFStudio
  betreffen: Kern (suite3), Kern + Produktion (suite5), Kern + Dreiecksgruppen (suite9). Etwa 215 MB.
- conformance/3mf-mcp: der MCP-Server des Konsortiums mit lib3mf (BSD-2-Clause); tests/check_3mf.mjs prueft
  damit die geschriebenen Dateien streng. Braucht Node.js 22 oder neuer.

tests/test_conformance.py ueberspringt die Teile, die fehlen - das heisst "nicht geprueft", nie "in Ordnung".

    python fetch_conformance.py           # beides holen (oder auffrischen)
    python fetch_conformance.py --suites  # nur die Konformitaetstests
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "conformance")
SUITES_URL = "https://github.com/3MFConsortium/test_suites.git"
MCP_URL = "https://github.com/3MFConsortium/3mf-mcp.git"
SUITES = ["suite3_core", "suite5_core_prod", "suite9_core_ext"]


def run(command: list[str], cwd: str) -> None:
    print(">", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True, shell=os.name == "nt" and command[0] == "npm")


def fetch(url: str, name: str, sparse: list[str] | None = None) -> str:
    folder = os.path.join(TARGET, name)
    if os.path.isdir(os.path.join(folder, ".git")):
        run(["git", "pull", "--ff-only"], folder)
        return folder
    os.makedirs(TARGET, exist_ok=True)
    command = ["git", "clone", "--depth", "1"] + (["--filter=blob:none", "--sparse"] if sparse else []) + [url, name]
    run(command, TARGET)
    if sparse:
        run(["git", "sparse-checkout", "set"] + sparse, folder)
    return folder


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suites", action="store_true", help="nur die Konformitaetstests holen")
    args = parser.parse_args()
    if shutil.which("git") is None:
        print("git fehlt - nichts geholt.")
        return 1
    fetch(SUITES_URL, "test_suites", SUITES)
    if args.suites:
        return 0
    if shutil.which("npm") is None:
        print("Node.js/npm fehlt - der MCP-Server wurde nicht gebaut; die strenge Pruefung bleibt aus.")
        return 1
    folder = fetch(MCP_URL, "3mf-mcp")
    run(["npm", "ci"], folder)
    run(["npm", "run", "build"], folder)
    return 0


if __name__ == "__main__":
    sys.exit(main())
