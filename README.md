# Werewolf

Jeu de Loup-Garou jouable en ligne de commande, avec 1 humain et 9 IA.
Toutes les IA (villageois et loups) sont contrôlées par un **LLM Groq** via l’API de texte.

## Règles de la v1

- La partie se joue à 10 joueurs : **2 loups** et **8 villageois**.  
- Le rôle de l’humain est tiré au hasard, mais comme il n’y a que 2 loups, il a statistiquement plus de chances d’être **villageois** que **loup**. 
- À chaque **nuit**, les loups choisissent une victime : un joueur meurt.  
- Les **loups gagnent** dès qu’ils ne sont plus minoritaires, c’est‑à‑dire quand le nombre de loups restants est **supérieur ou égal** au nombre de villageois encore en vie.  
- Les **villageois gagnent** dès que **tous les loups sont morts**.  
- Le joueur humain garde sa propre personnalité ; au contraire, les IA reçoivent un **rôle** (loup/villageois) et un **contexte de personnalité** spécifique qui influence leur façon de parler et de voter.  
- Les loups IA ne connaissent que les **noms de leurs coéquipiers loups** ; ils ne disposent d’aucune information spéciale sur les villageois.  
- Chaque IA possède uniquement **son propre historique de conversation** : aucune IA n’accède directement à l’historique interne des autres, même si toutes “entendent” les mêmes messages dans le débat.

## Pistes pour la V2

- Ajouter de **nouveaux rôles** (voyante, médecin, etc.) avec des pouvoirs spécifiques.  
- Enrichir les **mécaniques propres à chaque rôle** (visions, protections, capacités spéciales de vote).  
- Allonger la durée de la partie : plus de joueurs, nuits sans mort, rôles défensifs, paramètres de difficulté.  
- Créer un **frontend** (web ou desktop) pour afficher la discussion sous forme de chat, les fiches personnages et les votes, tout en réutilisant le moteur de jeu actuel en backend.
