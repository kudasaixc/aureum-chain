# Aureum Chain

Aureum Chain est une blockchain inspirée de Bitcoin (modèle UTXO, preuve de travail, transactions signées) livrée comme un nœud exécutable et un CLI.

## Fonctionnalités principales

- Modèle UTXO avec signatures ECDSA (SECP256K1).
- Preuve de travail (PoW) avec difficulté configurable.
- Mempool avec sélection des transactions par frais.
- API HTTP pour diffuser les transactions, miner, synchroniser et ajouter des pairs.
- Portefeuille local (clé privée + adresse) avec export JSON.

## Pré-requis

- Python 3.10+

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Démarrage rapide

1. **Initialiser la chaîne**

```bash
aureum-chain init --data-dir ~/.aureum_chain
```

2. **Créer un portefeuille**

```bash
aureum-chain wallet create --path ~/.aureum_chain/wallet.json
```

3. **Démarrer un nœud**

```bash
aureum-chain node --data-dir ~/.aureum_chain --host 0.0.0.0 --port 8332
```

4. **Miner un bloc**

```bash
aureum-chain mine <ADRESSE_DU_MINEUR>
```

5. **Envoyer une transaction**

```bash
aureum-chain tx <ADRESSE_DESTINATAIRE> <MONTANT>
```

## Mise en réseau

- **Ajouter des pairs**

```bash
aureum-chain peers http://127.0.0.1:8333 http://127.0.0.1:8334
```

- **Synchroniser**

```bash
aureum-chain sync
```

## API HTTP (extraits)

- `GET /status` → état du nœud (hauteur, hash, mempool)
- `GET /chain` → chaîne complète
- `POST /transactions/new` → nouvelle transaction
- `POST /mine` → minage manuel
- `POST /sync` → synchronisation avec les pairs

## Déploiement

Pour un déploiement immédiat, exécutez un service système ou un conteneur qui lance :

```bash
export AUREUM_DATA_DIR=~/.aureum_chain
uvicorn aureum_chain.node:create_app --factory --host 0.0.0.0 --port 8332 --proxy-headers
```

Vous pouvez configurer des volumes persistants pour `~/.aureum_chain` afin de conserver la chaîne et le mempool.

## Test manuel (propagation automatique)

1. **Démarrer deux nœuds avec des répertoires séparés**

```bash
aureum-chain node --data-dir ~/.aureum_chain_node1 --host 0.0.0.0 --port 8332
aureum-chain node --data-dir ~/.aureum_chain_node2 --host 0.0.0.0 --port 8333
```

2. **Ajouter les pairs**

```bash
curl -X POST http://127.0.0.1:8332/peers/add -H "Content-Type: application/json" -d '{"peers": ["http://127.0.0.1:8333"]}'
curl -X POST http://127.0.0.1:8333/peers/add -H "Content-Type: application/json" -d '{"peers": ["http://127.0.0.1:8332"]}'
```

3. **Soumettre une transaction et vérifier la propagation**

```bash
curl -X POST http://127.0.0.1:8332/transactions/new -H "Content-Type: application/json" -d '<TX_JSON>'
curl http://127.0.0.1:8333/status
```

4. **Miner sur le nœud 1 et vérifier la propagation du bloc**

```bash
curl -X POST http://127.0.0.1:8332/mine -H "Content-Type: application/json" -d '{"address": "<ADRESSE_DU_MINEUR>"}'
curl http://127.0.0.1:8333/status
```
