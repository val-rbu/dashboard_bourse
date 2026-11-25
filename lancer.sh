#!/usr/bin/env bash
# Lancement du tableau de bord (Mac / Linux) : ./lancer.sh
# La premiere fois, installe tout ce qu'il faut, puis ouvre l'application dans le navigateur.
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 n'est pas installe : https://www.python.org/downloads/"
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "Premiere installation, patientez..."
    python3 -m venv .venv && .venv/bin/python -m pip install --upgrade pip \
        && .venv/bin/python -m pip install -r requirements.txt || { echo "Echec de l'installation."; exit 1; }
fi

.venv/bin/python -m streamlit run app.py
