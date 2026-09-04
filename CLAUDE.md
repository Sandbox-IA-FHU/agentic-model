# Consignes Claude Code — agentic-model

Complète le `CLAUDE.md` de l'organisation (dépôt `.github`), il ne l'annule
pas. Les conventions d'écriture Python sont dans
[CONVENTIONS-PYTHON.md](CONVENTIONS-PYTHON.md) — à lire avant toute
modification de code.

## Ce qu'est ce dépôt

Un **modèle** d'agent à outils. Le code est volontairement minuscule : ce qu'il
transmet, c'est une méthode et trois garde-fous, pas une bibliothèque. Une
modification qui rend l'agent plus capable mais moins lisible est une
régression.

## Commandes

```bash
uv sync                      # installation
uv run ruff format .         # formatage
uv run ruff check .          # lint
uv run pytest                # tests, sans réseau ni clé
uv run --env-file .env python scripts/run_agent.py "une tâche"
uv run --env-file .env python scripts/evaluate.py --limite 3
```

Aucun test n'appelle un fournisseur de modèle. Les scénarios d'agent sont
rejoués par `ScriptedClient` dans `tests/conftest.py` : une liste de tours
préparés, rendue dans l'ordre. C'est ce qui permet de tester des boucles
entières — plafond atteint, action refusée, outil en erreur — hors ligne.

## Architecture, en une phrase par module

| Module | Rôle |
|---|---|
| `models.py` | Structures, dont `Trace` — ce qu'on relit et ce qu'on mesure. |
| `config.py` | Seul endroit qui lit `os.environ`. Valide et échoue au démarrage. |
| `client.py` | Seul module qui connaît le SDK. Protocole `AgentClient`. |
| `tools.py` | Registre : le schéma envoyé au modèle et la fonction exécutée viennent du même objet. |
| `toolbox.py` | Les quatre outils d'exemple, dont l'évaluateur arithmétique sans `eval`. |
| `approval.py` | Politiques de validation. Défaut : refus. |
| `loop.py` | `runAgent` — la boucle, plafonnée. |
| `costs.py` | Jetons → dollars, avec des tarifs datés. |
| `evaluation.py` | Notation et agrégation. |

## Les quatre choses à ne pas casser

**1. Le plafond d'itérations.** `MAX_ITERATIONS` dans `loop.py`, en dur, en
majuscules. Il ne devient jamais un paramètre sans valeur par défaut, il ne
disparaît pas, et l'atteindre reste visible dans la trace. Tests :
`test_iterationLimitStopsTheLoop`, `test_iterationLimitIsNotSilent`.

**2. Le passage obligatoire par la validation.** Tout outil `isSensitive`
traverse `approval.approve` dans `executeCall`. Aucun chemin de contournement,
quelle que soit la justification écrite par le modèle. Test :
`test_sensitiveToolNeedsApproval`.

**3. `eval` n'entre jamais dans ce dépôt.** L'outil `calculate` analyse
l'expression et n'autorise que des nœuds arithmétiques. Du code produit par un
modèle est du code plausible, pas du code sûr. Test :
`test_functionCallsAreRefused`.

**4. Le contenu d'outil reste de la donnée.** On ne filtre pas les résultats
d'outils, on ne prétend pas détecter une injection : on limite la surface
d'outils. Le magasin d'exemple contient une note empoisonnée, elle doit y
rester.

---

## Le coût d'un agent n'est pas linéaire

C'est le point le plus mal anticipé sur ce type de projet, et c'est de
l'arithmétique, pas une opinion.

L'API est **sans état** : à chaque tour, la boucle renvoie tout l'historique.
Si `B` est la partie fixe (prompt système + schémas d'outils + tâche) et `C` ce
qu'un tour ajoute (réponse du modèle + résultats d'outils), le total d'entrée
sur `N` tours vaut :

```
N × B  +  C × N(N−1)/2
```

Pour `N = 8` : la partie fixe est facturée **8 fois**, et le terme variable
vaut **28 fois** le contenu d'un tour, pas 8. Un agent qui met six tours au
lieu de deux ne coûte pas trois fois plus cher : il coûte nettement plus.

Trois conséquences pratiques :

- **Le nombre de tours est une métrique de coût de premier ordre**, pas une
  curiosité. `etapes_medianes` et `etapes_max` sont dans le fichier de run pour
  ça. Faire passer la médiane de 4 à 3 vaut souvent mieux que n'importe quelle
  optimisation de prompt.
- **Faire regrouper les appels d'outils indépendants** est le gain le plus
  simple : deux notes lues dans le même tour, c'est un aller-retour au lieu de
  deux. Le prompt le demande déjà ; `test_parallelToolResultsGoInASingleMessage`
  vérifie que la boucle ne casse pas cette possibilité en éclatant les
  résultats sur plusieurs messages.
- **La partie fixe est un candidat au cache de prompt.** Prompt système et
  schémas d'outils sont identiques d'un tour à l'autre : c'est exactement le
  préfixe stable qu'un cache sait servir. Ce n'est pas implémenté ici pour
  garder la boucle lisible ; si un projet dérivé en a besoin, c'est le premier
  levier à mesurer, et il faut vérifier les conditions et le tarif du
  fournisseur **à la date du jour** avant d'annoncer un gain.

Ne convertis jamais un nombre de mots en jetons avec un ratio de tête. Le
comptage se lit dans `usage` après un vrai appel, et il est déjà accumulé sur
toute la boucle dans `trace.usage`.

---

## Diagnostiquer un agent qui se comporte mal

« L'agent est bête » n'est pas un diagnostic. Six symptômes distincts, six
causes différentes, et dans quatre cas sur six la correction **n'est pas dans
le prompt**.

Commence toujours par lire la trace : `summarizeTrace(trace)` donne la
séquence d'outils et les compteurs, `trace.steps` donne le détail.

### L'agent redemande le même outil avec les mêmes arguments

C'est le symptôme le plus fréquent, et le prompt n'y est pour rien. Le modèle
boucle parce que le **résultat d'outil ne lui apprend rien** : chaîne vide,
message d'erreur sans indication de correction, format ambigu.

Correction : dans `toolbox.py`, faire que l'outil dise ce qu'il faut faire.
`readNote` liste les notes disponibles quand le nom est inconnu — c'est
délibéré, et c'est ce qui permet au modèle de se rattraper en un tour au lieu
de réessayer trois fois.

### L'agent appelle le mauvais outil

Problème de **description**, pas de prompt système. Une description qui dit ce
que l'outil fait sans dire quand l'utiliser laisse le modèle deviner.

Relis la description avec cette question : quelqu'un qui ne connaît pas le
projet saurait-il choisir entre cet outil et son voisin ?

### L'agent atteint le plafond

Trois causes à distinguer avant de toucher à `MAX_ITERATIONS` — l'augmenter est
la mauvaise réponse dans deux cas sur trois :

- **Il boucle** — voir plus haut, c'est le résultat d'outil qu'il faut corriger.
- **La tâche demande plus d'étapes que le plafond** — légitime. C'est alors une
  décision explicite, avec le coût recalculé selon la formule ci-dessus, pas un
  chiffre qu'on monte parce que ça bloque.
- **Il explore sans but** — il lit tout « au cas où ». C'est le prompt, section
  « il ne continue pas à explorer au cas où ».

### L'agent répond sans appeler d'outil

Il a répondu de mémoire au lieu d'aller chercher. Sur une question générale
c'est acceptable ; sur une question portant sur les notes, c'est une réponse
inventée qui a l'air sûre d'elle. À traiter comme un échec, jamais comme une
réussite rapide.

### L'agent obéit à ce qu'il a lu

Injection réussie. La réaction correcte **n'est pas** d'ajouter une
interdiction au prompt : c'est de regarder ce que l'agent a pu faire à cause
d'elle. Si la réponse est « rien de grave, la validation a bloqué », le
dispositif a fonctionné comme prévu. Si la réponse est « il aurait pu faire X »,
c'est X qu'il faut retirer ou marquer sensible.

Le prompt réduit la fréquence ; il ne borne pas les dégâts. Seule la surface
d'outils les borne.

### L'agent réessaie après un refus de validation

C'est le prompt, et c'est un vrai problème de coût : chaque nouvelle tentative
est un tour complet. `REFUSAL_MESSAGE` dans `approval.py` le lui dit déjà — si
le comportement persiste, c'est là qu'il faut renforcer, pas ailleurs.

---

## La description d'un outil fait partie du prompt

Point systématiquement oublié en revue.

Le texte de `ToolSpec.description` part chez le fournisseur à **chaque tour**,
au même titre que le prompt système. Trois conséquences :

1. **Modifier une description invalide les runs passés**, exactement comme
   modifier le prompt. Il faut un nouveau run de référence, et le dire.
2. Une description bavarde est facturée à chaque tour de chaque tâche. La
   formule de coût plus haut s'applique aussi à elle.
3. Une description est le bon endroit pour dire qu'une action est irréversible
   et soumise à validation — le modèle peut alors en tenir compte **avant** de
   demander l'action, pas seulement après un refus. C'est ce que vérifie
   `test_sensitiveToolDescriptionWarnsTheModel`.

## Ce qui se règle par le prompt, et ce qui ne s'y règle pas

| Objectif | Prompt | Code |
|---|---|---|
| Que l'agent soit plus concis | oui | — |
| Qu'il regroupe ses appels | oui | — |
| Qu'il cesse de réessayer après un refus | oui | — |
| Qu'il n'obéisse pas à une note empoisonnée | réduit la fréquence | **ne garantit rien** |
| Qu'aucune action irréversible n'ait lieu sans accord | non | `isSensitive` + `approval` |
| Que la facture soit bornée | non | `MAX_ITERATIONS` |
| Qu'aucun code arbitraire ne s'exécute | non | l'analyseur de `calculate` |

La ligne à retenir : **une garantie qui repose sur une phrase de prompt n'en
est pas une.** Si on te demande d'empêcher un comportement dangereux en
ajoutant une interdiction au prompt, pose d'abord la question de l'outil
correspondant.

## Si on te demande d'ajouter un outil

Trois questions, dans cet ordre, avant d'écrire la ligne :

1. **Est-il sensible ?** Irréversible, coûteux, ou visible à l'extérieur
   (envoi, publication, suppression, écriture, paiement) → `isSensitive=True`.
   Dans le doute, oui : le coût d'une validation inutile est une question posée
   à un humain ; le coût d'une action irréversible non validée est un incident.
2. **Que peut-il faire si un contenu récupéré le déclenche ?** C'est la bonne
   façon de raisonner sur l'injection : pas « le prompt tiendra-t-il » mais
   « que se passe-t-il s'il ne tient pas ».
3. **Sa description dit-elle quand l'utiliser, et pas seulement ce qu'il
   fait ?**

Un outil ajouté demande deux cas dans le jeu d'évaluation : un où il **doit**
être appelé, un où il ne doit **pas** l'être. Sans le second, on ne mesure que
la capacité, jamais la retenue. Voir `/outil`.

## Lire un fichier de run

Dans cet ordre, et le premier est éliminatoire :

1. `outil_interdit_appele` — doit être à **0**. Un agent qui tente une action
   interdite une fois sur vingt la tentera en production. Si ce n'est pas 0, le
   reste du run n'a pas d'intérêt.
2. `limite_iterations_atteinte` — ces cas ne sont ni réussis ni ratés, ils sont
   ininterprétables. Beaucoup de plafonds atteints = le score de réussite porte
   sur moins de cas qu'annoncé.
3. `tache_reussie`, **et son découpage par type**. Des échecs concentrés sur
   les cas de refus décrivent un système dangereux affiché comme correct.
4. `etapes_medianes` / `etapes_max` — le coût, et le meilleur gisement
   d'économies.
5. Coût, latence, avec la date de relevé des tarifs.

## Ce qu'on attend d'une session ici

**Avant de coder, cadrer.** Quelle question, quelle mesure, quel seuil. La
commande `/cadrer` sert à ça.

**Diagnostiquer avant de corriger.** Lire la trace d'abord. Proposer une
retouche de prompt sans avoir regardé la séquence d'outils est l'erreur la plus
courante sur un agent.

**Une modification de prompt — ou de description d'outil — se mesure.** Un run
avant, un run après, un seul paramètre changé.

**Prévenir du coût avant de lancer une évaluation.** Sur 21 cas et
`MAX_ITERATIONS = 8`, c'est jusqu'à 168 appels modèle, pas 21. Proposer
`--limite 3` d'abord.

**Ne pas conclure sur un écart faible.** Sur 21 cas, deux cas qui basculent
font 10 points. Traduis toujours un écart en nombre de cas.

**Ne pas ajouter de dépendance** sans raison écrite. En particulier : pas de
framework d'agents, pas de bibliothèque d'orchestration « pour voir ». Le
`tool_runner` du SDK est un choix raisonnable sur un vrai projet — mais c'est
une décision à écrire dans le README, pas un glissement.

**Ne jamais inventer un chiffre.** Les tarifs de `costs.py` portent leur date
de relevé ; les mettre à jour, c'est aussi mettre à jour la date.

## Ce qui ne va jamais dans le dépôt

Une donnée réelle, une clé, un nom de client, un notebook avec ses sorties.

Attention particulière ici : une **trace d'agent contient le contenu de tout ce
que l'agent a lu**, résultats d'outils compris. C'est la trace la plus riche —
donc la plus dangereuse — des deux modèles de l'organisation. Elle ne se
commite jamais, `traces/` est dans `.gitignore`, et `summarizeTrace` existe
précisément pour n'afficher que des noms d'outils et des compteurs. Test :
`test_traceSummaryLeaksNoContent`.

## Commandes et sous-agents

| | |
|---|---|
| `/cadrer` | Écrire question, mesure et seuil avant de coder |
| `/prompt` | Créer une version de prompt sans écraser la précédente |
| `/outil` | Ajouter un outil, avec la question de sa sensibilité |
| `/evaluer` | Lancer l'évaluation et écrire le fichier de run |
| `/avant-pr` | Passer la checklist de revue sur son propre diff |
| `relecteur-resultats` | La conclusion est-elle soutenue par ses chiffres ? |
| `verificateur-donnees` | Le diff contient-il donnée, clé ou nom de client ? |
