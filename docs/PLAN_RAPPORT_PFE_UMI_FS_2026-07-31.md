# Plan de production du rapport PFE — EnergyAI

**Université Moulay Ismaïl — Faculté des Sciences de Meknès**

**Filière présumée : Master SDIA — à confirmer sur le modèle officiel**

**Étudiant : Zouitni Salah Eddine — orthographe administrative à confirmer**

**Encadrant : M. Ali Oubelkacem — grade et intitulé à confirmer**

**Année universitaire : 2025–2026**
**Version du plan : 31 juillet 2026**

---

## 1. Décision éditoriale recommandée

Le rapport ne doit pas être présenté comme la simple construction d'une application de prévision. Son fil directeur le plus fort est un **parcours scientifique complet** : partir d'un article initial fourni par l'encadrant, tenter de le reproduire, identifier pourquoi des scores spectaculaires ne prouvent pas une capacité de prévision, corriger le protocole, comparer plusieurs familles de modèles modernes, puis industrialiser les modèles réellement validés dans une plateforme fiable.

### Titre recommandé

> **Prévision multi-horizon de la consommation électrique : audit méthodologique, comparaison de modèles profonds et industrialisation d'une plateforme fiable**

Version plus orientée produit :

> **EnergyAI : de l'audit des fuites de données à une plateforme fiable de prévision énergétique multi-horizon**

Le premier titre est plus académique. Le second est plus mémorable pour une soutenance, mais il faut vérifier si la filière accepte un nom de produit dans le titre officiel.

### Question de recherche

> Comment construire et industrialiser un système de prévision de la consommation électrique dont les performances restent valides lorsque les fuites de données, les séparations temporelles incorrectes et les métriques trompeuses sont éliminées ?

### Contributions à revendiquer

1. Une réplication critique du DEPM et une identification reproductible des sources de fuite ou d'ambiguïté méthodologique.
2. Une transition documentée d'une classification artificielle vers une vraie prévision continue multi-horizon.
3. Un protocole expérimental chronologique, avec prétraitement ajusté sur l'entraînement uniquement et comparaison à des baselines naïves.
4. Un benchmark progressif de modèles récurrents, convolutionnels et Transformers.
5. Une étude de généralisation sur plusieurs jeux de données et, dans la phase finale, sur des ménages connus et des ménages *cold-start*.
6. La sélection et l'empaquetage de modèles de production vérifiés pour 24 h et 168 h.
7. Une plateforme complète qui rend les prévisions, métriques, alertes, rapports et limites du modèle compréhensibles par l'utilisateur.

---

## 2. Conformité FS-UMI et page de garde

### 2.1 Éléments confirmés

- Le site officiel de la Faculté des Sciences de Meknès référence un document nommé **« Model page de garde »** dans ses documents de soutenance : <https://www.fs-umi.ac.ma/index.php/theses/>.
- L'UMI indique disposer d'une charte graphique validée par son conseil : <https://www.umi.ac.ma/decouverez-le-nouveau-site-web-de-luniversite-moulay-ismail/>.
- Le site FS-UMI renvoie actuellement une erreur serveur lors de la consultation directe. Le modèle exact n'a donc pas pu être téléchargé et vérifié le 31 juillet 2026.

Le lien identifié concerne la rubrique « Thèses ». Il prouve l'existence d'un modèle institutionnel, mais **pas que ce modèle est celui du PFE Master SDIA**. La première action du rapport est donc d'obtenir le fichier applicable au Master auprès du responsable de filière, du secrétariat ou de l'encadrant.

### 2.2 Règle impérative pour les logos

- Utiliser uniquement les fichiers officiels de l'UMI et de la Faculté des Sciences.
- Ne pas redessiner les logos et ne pas utiliser une vignette issue d'un moteur de recherche.
- Conserver les proportions, couleurs et zones de respiration.
- Préférer un SVG, PDF vectoriel ou PNG transparent d'au moins 1000 px de large.
- Archiver la source et la date d'obtention dans `report/assets/logos/SOURCES.md`.

### 2.3 Structure de page de garde à préparer

La disposition exacte sera copiée depuis le modèle officiel. Les champs à réunir sont :

1. Logo UMI et logo Faculté des Sciences.
2. « Université Moulay Ismaïl » et « Faculté des Sciences de Meknès ».
3. Département et intitulé administratif exact du Master.
4. Mention « Projet de fin d'études » ou formulation officielle.
5. Titre final validé.
6. Nom complet de l'étudiant selon la CIN et le dossier universitaire.
7. Nom, grade, laboratoire et établissement de l'encadrant.
8. Organisme d'accueil, si applicable.
9. Composition du jury, avec grades et rôles.
10. Date de soutenance et année universitaire 2025–2026.

### 2.4 Mise en page provisoire — non présentée comme règle officielle

Tant que la fiche de consignes Master n'est pas obtenue, utiliser ces valeurs comme paramètres de travail réversibles :

| Élément | Valeur de travail | Statut |
|---|---:|---|
| Format | A4 | à confirmer |
| Marges | 2,5 cm ; reliure 0,5 cm si nécessaire | à confirmer |
| Corps | Times New Roman 12 pt ou police imposée par la filière | à confirmer |
| Interligne | 1,5 | à confirmer |
| Texte | justifié, veuves/orphelines évitées | recommandation |
| Titres 1 / 2 / 3 | 16 / 14 / 12 pt, styles automatiques | recommandation |
| Légendes | 10 pt, numérotation par chapitre | recommandation |
| Pagination | romaine pour le préliminaire, arabe pour le corps | à confirmer |
| Citations | IEEE numérique, sauf norme imposée | à confirmer |
| Langue | français, résumés français et anglais | hypothèse de travail |

Ne jamais graver ces valeurs manuellement sur chaque page. Elles doivent être définies dans des styles Word ou LaTeX afin de pouvoir appliquer les règles officielles en une seule modification.

---

## 3. Positionnement éthique de l'article initial

L'article DEPM doit être inclus, car il est le point de départ du PFE et la source du pivot scientifique. Il faut toutefois écrire **« article initial fourni/proposé par l'encadrant »**, et non « article de l'encadrant », sauf preuve qu'il en est auteur.

### 3.1 Article de départ

Ragupathi et al., *Prediction of electricity consumption using an innovative deep energy predictor model for enhanced accuracy and efficiency*, **Energy Reports**, 2024, DOI : <https://doi.org/10.1016/j.egyr.2024.11.018>.

Le papier annonce notamment une accuracy de 98 % pour un modèle combinant XGBoost, DNN et Cascaded ResNet. La réplication locale a initialement produit environ 99,29 %, mais ce score ne doit plus être présenté comme une amélioration de l'état de l'art.

### 3.2 Formulations à employer

| Formulation à éviter | Formulation scientifique recommandée |
|---|---|
| « Le modèle triche » | « La performance est dominée par une information directement ou physiquement dérivée de la cible. » |
| « L'article est faux » | « Plusieurs résultats n'ont pas pu être réconciliés avec la taille du jeu de données et le protocole décrit. » |
| « Matrice fabriquée » | « La somme des cellules visibles de la matrice est incompatible avec le volume annoncé ; l'article ne fournit pas l'explication nécessaire. » |
| « Texte plagié » | « Des passages et termes hors domaine ont été observés ; une analyse de similarité formelle serait nécessaire avant toute conclusion. » |
| « Méthode sans valeur » | « Le protocole décrit ne permet pas d'établir une performance de prévision hors échantillon. » |

### 3.3 Constats à documenter séparément

Le chapitre doit distinguer trois niveaux de preuve :

- **Affirmation de l'article** : ce que les auteurs déclarent explicitement.
- **Observation de réplication** : ce que le code et les expériences du PFE reproduisent.
- **Limite ou hypothèse** : ce qui reste impossible à confirmer faute de code, de seuil, de split ou de détails.

Les problèmes techniques à présenter sont :

1. **Fuite directe de cible** : certaines premières implémentations conservent `Global_active_power` parmi les variables alors que la classe cible en est dérivée.
2. **Proxy physique** : `Global_intensity` et `Voltage` permettent d'approximer la puissance par la relation `P ≈ V × I`.
3. **Fenêtres non décalées** : certaines statistiques glissantes incluent la valeur courante de la cible.
4. **Prétraitement avant séparation** : scaler et PCA ajustés sur l'ensemble des données transmettent de l'information du test vers l'entraînement.
5. **Split aléatoire** : une séparation aléatoire de mesures temporelles très corrélées surestime la généralisation future.
6. **Tâche mal alignée** : une classification haute/basse consommation n'est pas équivalente à une prévision continue de consommation.
7. **Seuil de classe insuffisamment défini** : la reproduction exacte de la cible annoncée devient ambiguë.
8. **Métriques et échelle** : MAE/RMSE doivent être rapportées après transformation inverse et avec une unité physique.
9. **Matrice de confusion** : les totaux observés doivent être confrontés au nombre de lignes et au protocole d'échantillonnage.

La régression logistique à 99,4 % avec variables fuyardes est un **test de diagnostic** : elle montre que la complexité du DEPM n'est pas nécessaire pour obtenir un score élevé lorsque la cible est reconstructible. Ce résultat ne doit pas être présenté comme un modèle final.

---

## 4. Inventaire des sources à exploiter

### 4.1 Documents et articles locaux

| Source | Chemin | Utilisation dans le rapport |
|---|---|---|
| Article DEPM initial | `C:/Users/salah/Documents/MASTER/PFE/paper/Subject-main.pdf` | point de départ, protocole annoncé, audit critique |
| Résumé initial en français | `C:/Users/salah/Documents/MASTER/PFE/paper/Résumé du sujet.pdf` | contexte donné au démarrage, à ne pas citer comme résultat indépendant |
| Article Stacked LSTM Snapshot Ensemble | `docs/research/paper.pdf` | revue de littérature et examen critique de métriques très élevées |
| Article CNN–Bi-LSTM / EECP-CBL | `docs/research/new paper/applsci-09-04237.pdf` | pivot vers la prévision continue et réplication CNN–Bi-LSTM |
| Présentation de progression | `docs/PFE Progress_ DEPM Analysis & Pivot (2).pdf` | chronologie, fuite `P = V × I`, pivot ; formulations à neutraliser |
| Audit complet de l'application | `docs/PFE_FULL_APP_AUDIT_2026-07-31.md` | preuves d'architecture, qualité, sécurité et tests |
| Plan d'amélioration jury | `docs/JURY_IMPACT_IMPLEMENTATION_PLAN_2026-07-31.md` | perspectives produit et soutenance, pas résultats déjà réalisés |

### 4.2 Ancien dossier PFE

Le dossier `C:/Users/salah/Documents/MASTER/PFE` n'est pas un dépôt Git, mais il contient la meilleure trace de la phase exploratoire :

- `notebooks/DEPM_Implementation.ipynb` et `DEPM_Deep_Energy_Predictor_Model.ipynb` ;
- `notebooks/DEPM_Feature_Ablation.ipynb` ;
- `notebooks/depm-proposed.ipynb`, `depm-variants-comparison.ipynb`, `depm-ablation-study.ipynb` ;
- `notebooks/LSTM_Energy_Predictor.ipynb` ;
- `notebooks/EDA_Exploration.ipynb` ;
- `models/models_depm/{scaler.pkl,pca.pkl,dnn.pth,resnet.pth}` ;
- `models/models_lstm/lstm.pth` ;
- `results/` et `results_lstm/` pour les graphiques historiques.

Les scores historiques 99,29 % DEPM et 85,15 % LSTM doivent apparaître uniquement dans une section **« résultats initiaux invalidés ou non comparables »**, accompagnés des raisons. Ils ne doivent pas être réutilisés dans le résumé, la conclusion ou la page des contributions.

### 4.3 Dépôt Git et points de contrôle

Les commits servent de journal expérimental. Les étapes minimales à citer dans une annexe de traçabilité sont :

| Date | Commit | Étape |
|---|---|---|
| 10–15 avril | `43f5cab`, `ed3c48e`, `b96fef0` | initialisation, extraction du papier, première implémentation DEPM |
| 2 mai | `8daf16c` | comparaison équitable et investigation des fuites |
| 5–11 mai | `ea4e8de`, `c40b120`, `71ca537`, `6f50535` | réplication, version *no-leak*, variantes et test Steel Industry |
| 17–22 mai | `87a70c1`, `a653dcf`, `2c0cb9`, `26e7ecf`, `5999ecc`, `8813aca` | pivot régression, CNN–Bi-LSTM, EECP-CBL, application de prévision, PatchTST |
| juin | `4a5cb69`, `695b695`, `c61cb66` | API, sécurité, frontend, registre de modèles |
| 17–20 juillet | `92d9ab2`, `a6d1683`, `07b43b5`, `9525d3f` | contrats fiables, TFT 24 h, artefacts fixes, release PFE |
| 22–27 juillet | `9226b56`, `baacbf2`, `1e67921` | horizon 168 h, deux horizons livrés, Product V1 |

Tags à figer dans l'annexe :

- `v0.1.0` : recherche et checkpoints historiques ;
- `ml-pipeline-ready` ;
- `v0.1.0-phase1`, `v0.2.0-training`, `v0.3.0-registry` ;
- `phase2-forecast-stable` ;
- `v2.5-production-stable`, `v2.6-hardened` ;
- commit de release PFE `9525d3f` ;
- commit Product V1 `1e67921`.

Pour chaque capture ou tableau reproduit depuis Git, enregistrer le commit exact dans la légende ou dans un registre de figures.

---

## 5. Catalogue des articles, architectures et essais

Le rapport doit séparer **lu**, **implémenté**, **reproduit**, **benchmarked** et **déployé**. Une lecture d'article n'est pas une reproduction ; un notebook qui ne termine pas n'est pas un résultat ; un checkpoint historique n'est pas nécessairement un modèle de production.

| Référence ou famille | Statut réel à raconter | Jeu(x) de données | Place dans le mémoire |
|---|---|---|---|
| DEPM — Ragupathi et al. 2024 | reproduit, audité, variantes testées ; protocole initial invalidé pour la prévision | IHEPC, Steel Industry | étude de cas centrale du chapitre 3 |
| Stacked LSTM Snapshot Ensemble — Alghamdi et al. 2024, DOI `10.26599/BDMA.2023.9020030` | article étudié ; ancien LSTM local, mais pas de reproduction exacte FFT + snapshots + méta-learner démontrée | IHEPC + météo dans l'article | état de l'art et discussion critique des scores extraordinaires |
| EECP-CBL — Le et al. 2019, DOI `10.3390/app9204237` | réplication CNN–Bi-LSTM et expériences de régression | IHEPC | premier pivot rigoureux vers la prévision continue |
| LSTM, BiLSTM, GRU, BiGRU, DNN + XGBoost | variantes DEPM et modèles autonomes entraînés | IHEPC | ablation et preuve que l'architecture n'est pas le problème principal |
| CNN–BiLSTM baseline | implémenté et checkpointé | IHEPC, ECL | baseline profonde récurrente |
| TSMixer | notebook/code exploratoire ; confirmer les runs achevés avant de publier des chiffres | IHEPC | architecture légère explorée |
| PatchTST — arXiv `2211.14730` | implémenté, entraîné, plusieurs horizons et variantes avancées | IHEPC, ECL | benchmark Transformer patché |
| iTransformer — arXiv `2310.06625` | entraîné sur ECL ; meilleur du benchmark ECL local aux horizons enregistrés | ECL | benchmark multivarié moderne |
| xPatch — arXiv `2412.17323` | entraîné sur ECL | ECL | modèle de comparaison récent |
| TimePro — arXiv `2505.20774` | intégration tentée ; dépendances CUDA spécifiques, statut des runs à documenter comme succès ou échec | ECL | essai récent et leçon de reproductibilité logicielle |
| TimeMixer++ — arXiv `2410.16032` | implémentation publique PyPOTS prévue/tentée, pas reproduction officielle | ECL | limite de reproductibilité et comparaison si métriques valides |
| Global TFT — Lim et al., DOI `10.1016/j.ijforecast.2021.03.012` | entraîné, sélectionné et déployé | Low Carbon London | modèle final 24 h et 168 h |
| Global N-BEATS — Oreshkin et al., arXiv `1905.10437` | entraîné comme fallback et candidat mensuel | Low Carbon London | candidat secondaire et ablation |
| MultiCycleNet-adapted | entraîné pour les agrégats mensuels ; origine exacte de l'architecture à verrouiller avant citation | Low Carbon London | expérience mensuelle, pas capacité produit actuellement exposée |
| Baselines saisonnière, persistance et modèles ML classiques | obligatoires dans les comparaisons | tous selon expérience | référence minimale pour prouver l'utilité réelle du deep learning |

Le benchmark ECL achevé actuellement contient des métriques pour **iTransformer, PatchTST, xPatch et CNN–BiLSTM** aux horizons 24, 96, 192, 336 et 720. TimePro et TimeMixer++ ne doivent obtenir une ligne de résultats que si leurs fichiers `metrics.json` prouvent un run réussi.

---

## 6. Structure détaillée proposée du rapport

Objectif de longueur : **90 à 120 pages de corps**, hors annexes, à ajuster dès réception des règles FS-UMI.

### Pages préliminaires — 8 à 12 pages

1. Page de garde officielle.
2. Dédicace — facultative, une page maximum.
3. Remerciements — une page.
4. Résumé français : problème, protocole corrigé, résultats finaux, plateforme ; 250–350 mots.
5. Abstract anglais : traduction scientifique contrôlée, pas mot à mot.
6. Mots-clés / Keywords.
7. Table des matières automatique.
8. Liste des figures.
9. Liste des tableaux.
10. Liste des acronymes : DEPM, IHEPC, ECL, LCL, TFT, LSTM, MAE, RMSE, MASE, sMAPE, R², API, JWT, RBAC, etc.

### Introduction générale — 4 à 6 pages

- Contexte énergétique et besoin de prévisions exploitables.
- Limite des scores ML lorsqu'ils ne respectent pas la causalité temporelle.
- Problématique et questions de recherche.
- Objectifs scientifiques et produit.
- Méthodologie globale.
- Contributions.
- Organisation du mémoire.

### Chapitre 1 — Contexte, besoin et cadrage — 8 à 12 pages

1. Prévision de charge et gestion énergétique.
2. Cas d'usage : anticipation, budget, alertes et décision.
3. Différence entre classification, régression, prévision un pas et multi-horizon.
4. Parties prenantes et exigences fonctionnelles.
5. Contraintes : qualité des données, confidentialité, explicabilité, latence, *cold-start*.
6. Cahier des charges de la plateforme.

**Figures** : carte des parties prenantes, workflow métier, définition graphique des horizons 24 h/168 h.

### Chapitre 2 — État de l'art raisonné — 12 à 16 pages

1. Modèles statistiques et baselines saisonnières.
2. Régression et arbres de décision.
3. RNN, LSTM, GRU et BiLSTM.
4. CNN–LSTM et CNN–BiLSTM.
5. Transformers de séries temporelles : PatchTST, iTransformer, xPatch, TimePro, TimeMixer++.
6. Modèles globaux : N-BEATS et TFT.
7. Ensembles et snapshot ensembles.
8. Risques méthodologiques : fuite, horizon, split, échelle, métriques, sélection sur le test.
9. Tableau comparatif des articles avec données, entrée, cible, horizon, split, métriques, code officiel et limites.

Ce chapitre doit regrouper les travaux par **famille et problème résolu**, pas consacrer une sous-section isolée à chaque PDF.

### Chapitre 3 — Réplication critique du DEPM — 15 à 20 pages

1. Contexte : article fourni par l'encadrant et objectifs de réplication.
2. Jeu IHEPC et variables physiques.
3. Architecture annoncée : Cascaded ResNet, DNN et XGBoost.
4. Reconstruction du pipeline initial.
5. Reproduction des résultats élevés.
6. Audit de la cible et des caractéristiques.
7. Démonstration de la fuite directe et du proxy `P ≈ V × I`.
8. Effet du split aléatoire, du scaler/PCA global et des fenêtres non décalées.
9. Comparaison DEPM / régression logistique / variantes sans fuite.
10. Incohérences documentaires non résolues : seuil, matrice, échelle et reproductibilité.
11. Conclusion : pourquoi le problème doit être reformulé en prévision continue.

**Tableau central obligatoire** : résultat historique, source de fuite, correction, résultat après correction, interprétation.

### Chapitre 4 — Reformulation et protocole expérimental fiable — 12 à 16 pages

1. Cible continue et horizons opérationnels.
2. Création de fenêtres strictement causales.
3. Split chronologique train/validation/test.
4. Ajustement des scalers sur le train uniquement.
5. Données IHEPC, Steel Industry, ECL et Low Carbon London : rôles différents.
6. Gestion des valeurs manquantes et unités.
7. Baselines saisonnières et de persistance.
8. Métriques : MAE/RMSE en unités physiques, sMAPE, MASE, biais, R² global et macro.
9. Protocole de sélection : validation pour choisir, test final utilisé une seule fois.
10. Répétabilité : graines, versions, checkpoints, manifestes et hashes.

**Figure centrale** : comparaison visuelle entre pipeline fuyard et pipeline causal.

### Chapitre 5 — Expériences, benchmarks et sélection — 18 à 24 pages

1. CNN–BiLSTM / EECP-CBL sur IHEPC.
2. Expériences DEPM corrigées et test Steel Industry.
3. PatchTST et modèles longue portée historiques.
4. Benchmark ECL : iTransformer, PatchTST, xPatch, CNN–BiLSTM ; tentatives TimePro/TimeMixer++.
5. Passage du benchmark multivarié à la contrainte produit `timestamp + energy_kwh`.
6. Benchmark global sur ménages Low Carbon London.
7. Séparation ménages connus / *cold-start*.
8. Comparaison TFT / N-BEATS / MultiCycleNet / baselines.
9. Analyse par horizon, distribution des ménages et p90.
10. Temps d'entraînement, paramètres et coût d'inférence.
11. Choix final et limites.

**Résultats finaux à mettre en avant** :

| Horizon | Modèle de production | MAE macro *cold-start* | Baseline saisonnière | Amélioration | Ménages meilleurs que la baseline |
|---|---|---:|---:|---:|---:|
| 24 h | Global TFT | 0,184928 kWh | 0,251540 kWh | 26,48 % | 99,0 % |
| 168 h | Global TFT | 0,197322 kWh | 0,249055 kWh | 20,77 % | 98,40 % |

Ces valeurs doivent être relues directement depuis les manifestes de production au moment de générer le mémoire. Ne pas recopier des métriques depuis une ancienne présentation.

Le résultat mensuel doit être présenté comme expérimental : les R² macro négatifs indiquent une généralisation insuffisante pour une promesse produit forte, même si la MAE moyenne bat la baseline saisonnière.

### Chapitre 6 — Conception et réalisation de la plateforme — 18 à 24 pages

1. Vision fonctionnelle et parcours utilisateur.
2. Architecture générale : Next.js, FastAPI, PostgreSQL, Redis, worker et Docker.
3. Modèle de données et diagrammes UML.
4. Authentification JWT, RBAC et isolation des données.
5. Import de consommation et validation des CSV.
6. Service de prévision et contrat d'artefact.
7. Gestion des horizons 24 h et 168 h.
8. Dashboard, centre de prévision, historique, alertes et rapports.
9. Explicabilité et affichage honnête des métriques.
10. Temps réel et WebSocket.
11. Observabilité, santé des services et gestion des erreurs.
12. Déploiement Docker et configuration.
13. Choix UI/UX et accessibilité.

**Figures** : architecture en couches, séquence d'une prévision, schéma de données, captures annotées du parcours complet.

### Chapitre 7 — Validation, qualité et discussion — 10 à 14 pages

1. Stratégie de tests backend, frontend, intégration et parcours utilisateur.
2. Résultat actuel : 100/100 tests backend dans l'environnement PostgreSQL isolé.
3. Tests des contrats d'artefacts et des horizons.
4. Sécurité : authentification, autorisations, validation d'entrée, SSRF et secrets.
5. Vérification des services Docker et états de santé.
6. Limites scientifiques : transfert géographique, météo, dérive, incertitude, horizon mensuel.
7. Limites produit : données réelles disponibles, monitoring modèle, expérience mobile, démonstration.
8. Menaces à la validité : interne, externe, de construction et de conclusion.
9. Comparaison finale aux objectifs initiaux.

### Conclusion générale et perspectives — 3 à 5 pages

- Réponse directe à la problématique.
- Contributions effectivement démontrées.
- Leçon principale : une métrique honnête est plus utile qu'un score spectaculaire obtenu avec fuite.
- Perspectives : quantiles/calibration, météo, données marocaines, dérive, réentraînement, horizon mensuel, déploiement cloud et étude utilisateur.

---

## 7. Annexes obligatoires

1. **A — Matrice de traçabilité** : exigence → fonctionnalité → test → preuve → commit.
2. **B — Chronologie Git complète** : commits et tags clés.
3. **C — Catalogue des notebooks** : objectif, données, statut, fuite connue, résultat exploitable ou non.
4. **D — Inventaire des checkpoints** : chemin, architecture, horizon, dataset, hash SHA-256, statut `archive/candidate/production`.
5. **E — Hyperparamètres finaux** des modèles retenus.
6. **F — Résultats détaillés** par ménage, horizon et seed si disponibles.
7. **G — API** : endpoints principaux et exemples de contrats, pas tout le code.
8. **H — Modèle de données et UML**.
9. **I — Plan de tests et résultats complets**.
10. **J — Guide d'installation reproductible Docker**.
11. **K — Déclaration d'utilisation d'outils d'IA**, selon les règles de la filière.

Le code source complet reste dans le dépôt. Les annexes ne doivent contenir que des extraits qui soutiennent une décision ou une preuve.

---

## 8. Figures et tableaux à produire

### Figures prioritaires

1. Chronologie du PFE : réplication → fuite → pivot → benchmark → produit.
2. Relation physique `P ≈ V × I` et mécanisme de fuite.
3. Pipeline initial versus pipeline causal corrigé.
4. Architecture DEPM reproduite.
5. Architectures CNN–BiLSTM, PatchTST/iTransformer et Global TFT simplifiées.
6. Découpage chronologique train/validation/test.
7. Distribution des erreurs par ménage, pas seulement une moyenne.
8. Prévision versus réel pour cas médian, bon cas et cas difficile.
9. Comparaison MAE aux baselines pour 24 h et 168 h.
10. Architecture complète de la plateforme.
11. Diagramme de séquence d'une demande de prévision.
12. Parcours de démonstration en 5 écrans maximum.

### Tableaux prioritaires

1. Comparaison critique de tous les articles.
2. Taxonomie des fuites et corrections.
3. Inventaire des datasets.
4. Hyperparamètres et budgets d'entraînement.
5. Leaderboard ECL.
6. Leaderboard Low Carbon London, cohortes connues et *cold-start*.
7. Sélection de production par horizon.
8. Tests et couverture des risques.
9. Limites et plans de mitigation.

Chaque figure doit être générée depuis une source traçable, exportée à 300 dpi ou en vectoriel, et accompagnée du script/notebook et du commit utilisés.

---

## 9. Gestion des checkpoints et des métriques

### 9.1 Classification des artefacts

- **Archive historique** : modèles DEPM, LSTM/GRU/BiLSTM/BiGRU et anciens modèles 24/168/720 h du tag `v0.1.0`.
- **Benchmark** : checkpoints ECL et résultats des modèles récents.
- **Candidat produit** : Global N-BEATS, MultiCycleNet-adapted et autres finalistes LCL.
- **Production** : uniquement les artefacts référencés par les manifestes actifs du backend.

### 9.2 Source de vérité finale

- `backend/model_artifacts/global_tft_24h/manifest.json` ;
- `backend/model_artifacts/global_tft_168h/manifest.json` ;
- `models/lcl_global_forecasting/full_selected_v1/leaderboard.csv` ;
- `models/lcl_global_forecasting/full_selected_v1/production_candidates.json` ;
- `models/ecl_deep_benchmark/leaderboard.csv` pour le benchmark ECL, jamais pour une promesse produit résidentielle individuelle.

### 9.3 Registre à créer avant rédaction des résultats

Créer `report/evidence/model_registry.csv` avec :

`artifact_id, model, dataset, target, lookback, horizon, split, scaler_scope, seed, checkpoint_path, sha256, metrics_path, commit, status, limitation`.

Un chiffre ne peut entrer dans le résumé ou la conclusion que s'il possède une ligne complète dans ce registre.

---

## 10. Bibliographie et règles de citation

1. Utiliser Zotero ou un fichier BibTeX unique.
2. Importer les métadonnées depuis DOI/arXiv, puis contrôler manuellement auteurs, année, revue et pages.
3. Citer la source primaire d'une architecture, pas un blog ou une implémentation tierce.
4. Pour le code, citer le dépôt officiel et le commit/version utilisé.
5. Citer les datasets avec leur DOI ou page officielle.
6. Ne jamais citer une ancienne présentation interne comme preuve d'une affirmation scientifique ; remonter au notebook, au CSV ou au papier.
7. Ne pas comparer des métriques calculées à des échelles ou horizons différents dans un même classement.
8. Pour toute adaptation — par exemple MultiCycleNet-adapted — décrire explicitement ce qui diffère du papier.
9. Faire un contrôle anti-plagiat et un contrôle des paraphrases avant livraison.

Références primaires déjà verrouillées :

- DEPM : <https://doi.org/10.1016/j.egyr.2024.11.018>
- Stacked LSTM Snapshot Ensemble : <https://doi.org/10.26599/BDMA.2023.9020030>
- CNN–BiLSTM / EECP-CBL : <https://doi.org/10.3390/app9204237>
- PatchTST : <https://arxiv.org/abs/2211.14730>
- iTransformer : <https://arxiv.org/abs/2310.06625>
- xPatch : <https://arxiv.org/abs/2412.17323>
- TimeMixer++ : <https://arxiv.org/abs/2410.16032>
- TimePro : <https://arxiv.org/abs/2505.20774>
- TFT : <https://doi.org/10.1016/j.ijforecast.2021.03.012>
- N-BEATS : <https://arxiv.org/abs/1905.10437>
- UCI ECL : <https://doi.org/10.24432/C58C86>

---

## 11. Arborescence de travail recommandée

```text
report/
├── source/
│   ├── report.docx                 # ou main.tex après décision
│   ├── bibliography.bib
│   └── glossary.csv
├── assets/
│   ├── logos/
│   │   └── SOURCES.md
│   ├── figures/
│   ├── screenshots/
│   └── diagrams/
├── evidence/
│   ├── model_registry.csv
│   ├── figure_registry.csv
│   ├── commit_timeline.csv
│   ├── notebook_catalog.csv
│   └── test_evidence/
├── exports/
│   ├── PFE_ZOUITNI_Salah_Eddine_draft.pdf
│   └── PFE_ZOUITNI_Salah_Eddine_final.pdf
└── qa/
    ├── compliance_checklist.md
    ├── citation_checklist.md
    └── final_pdf_checklist.md
```

### Format source recommandé

Utiliser **Word/DOCX** si le modèle FS-UMI est fourni sous Word, afin de préserver exactement la page de garde. Utiliser LaTeX seulement si la filière le permet et si la page de garde peut être reproduite sans altération. Dans les deux cas, générer automatiquement sommaire, listes, renvois et bibliographie.

---

## 12. Plan d'exécution

| Phase | Durée indicative | Livrable | Critère de sortie |
|---|---:|---|---|
| 0. Conformité | 0,5–1 jour | modèle officiel, logos, consignes | validation écrite ou fichier officiel archivé |
| 1. Gel des preuves | 1–2 jours | registres modèles/notebooks/commits | chaque chiffre est traçable |
| 2. Bibliographie | 1 jour | Zotero/BibTeX nettoyé | DOI, auteurs et statuts vérifiés |
| 3. Chapitres 3–5 | 3–4 jours | cœur scientifique | méthodes, résultats et limites complets |
| 4. Chapitres 1–2 | 2 jours | cadrage et état de l'art | lien direct avec la problématique |
| 5. Chapitres 6–7 | 2–3 jours | réalisation et validation | preuves app et tests intégrées |
| 6. Introduction/conclusion | 1 jour | récit cohérent | contributions strictement démontrées |
| 7. Visuels et annexes | 1–2 jours | figures, tableaux, annexes | sources et commits enregistrés |
| 8. Mise en forme | 1 jour | PDF candidat | règles FS-UMI respectées |
| 9. Relecture et QA | 1–2 jours | PDF final | zéro lien cassé, erreur ou chiffre orphelin |

Ordre de rédaction recommandé : **chapitre 3 → chapitre 4 → chapitre 5 → chapitre 6 → chapitre 7 → chapitre 2 → chapitre 1 → introduction → conclusion → résumé**. Le résumé est écrit en dernier.

---

## 13. Contrôles qualité avant dépôt

### Scientifique

- [ ] Toutes les fenêtres sont causales et les splits sont explicités.
- [ ] Tous les scalers/PCA publiés sont ajustés sur le train seulement.
- [ ] Chaque résultat précise dataset, cible, horizon, unité et cohorte.
- [ ] Les baselines figurent à côté des modèles profonds.
- [ ] Les anciens scores fuyards sont marqués invalidés/non comparables.
- [ ] Aucun run échoué n'est présenté comme une expérience achevée.
- [ ] Les métriques mensuelles négatives ou faibles ne sont pas masquées.
- [ ] Les limites et menaces à la validité sont explicites.

### Institutionnel et rédactionnel

- [ ] Page de garde issue du modèle Master applicable.
- [ ] Logos officiels, non déformés.
- [ ] Noms, grades, jury, date et année vérifiés.
- [ ] Styles, marges, pagination et bibliographie conformes.
- [ ] Toutes les figures sont lisibles à 100 % et ont une source.
- [ ] Tous les tableaux tiennent dans les marges.
- [ ] Tous les renvois, numéros et entrées de sommaire sont à jour.
- [ ] Orthographe française et cohérence terminologique relues.
- [ ] Abstract relu par une personne maîtrisant l'anglais scientifique.

### Produit et reproductibilité

- [ ] Le commit final du rapport et le commit produit sont enregistrés.
- [ ] Les services Docker démarrent depuis une installation propre.
- [ ] Les tests automatisés sont rejoués et leurs logs archivés.
- [ ] Les manifestes 24 h et 168 h correspondent aux poids livrés.
- [ ] Les captures montrent des données et métriques réelles.
- [ ] Les secrets, comptes et données personnelles sont absents du PDF et du dépôt public.

### Vérification du PDF final

1. Exporter en PDF/A si demandé.
2. Vérifier l'incorporation des polices.
3. Rendre toutes les pages en images et inspecter visuellement la couverture, les pages de début, chaque figure/tableau et les annexes.
4. Tester les signets, la table des matières et les liens.
5. Rechercher les chaînes `TODO`, `TBD`, `à confirmer`, chemins locaux, erreurs de référence et citations manquantes.
6. Comparer le nombre de pages et la taille du fichier aux limites de dépôt.

---

## 14. Informations à obtenir avant la génération du rapport

Ces points ne bloquent pas la collecte des preuves, mais bloquent la version finale :

1. Modèle de page de garde propre au Master/PFE.
2. Règlement de rédaction : langue, police, marges, longueur, reliure et format de citation.
3. Intitulé officiel complet de la filière et du département.
4. Titre définitif approuvé.
5. Nom administratif, grade et laboratoire de l'encadrant.
6. Composition et grades du jury.
7. Date de soutenance.
8. Organisme d'accueil et encadrant externe, s'il y en a un.
9. Autorisation ou format exigé pour la déclaration d'usage de l'IA.

---

## 15. Résultat attendu

Le rapport final doit permettre au jury de vérifier trois choses sans dépendre du discours oral :

1. **Le travail scientifique est honnête** : les erreurs initiales sont reconnues, expliquées et corrigées.
2. **La contribution est mesurable** : les modèles finaux battent une baseline pertinente sur un protocole causal et sur des ménages *cold-start*.
3. **Le produit est réel** : les artefacts sélectionnés sont intégrés à une application testée, sécurisée et reproductible.

Le point le plus différenciant du PFE n'est donc pas « obtenir 99 % ». C'est d'avoir démontré pourquoi ce nombre pouvait être trompeur, puis d'avoir construit une chaîne complète où chaque promesse est soutenue par une preuve traçable.
