# 🌡️ Automatisation de Chauffage Intelligent

Ce projet a été réalisé dans le cadre de mon projet de fin d'études de BTS CIEL. 

## 🎯 Objectif
Créer un système complet pour automatiser l'allumage de radiateurs connectés uniquement lorsque les salles sont occupées, en se basant sur les emplois du temps de l'établissement (EcoleDirecte).

## 🛠️ Technologies utilisées
*   **Backend & API :** Python (FastAPI) pour créer une API REST communiquant en JSON.
*   **Base de données :** SQLite (pour l'historique des températures).
*   **Système & Réseau :** Hébergement sous Linux (Raspberry Pi), automatisation des services avec Systemd.
*   **Frontend :** HTML, CSS, JavaScript (connexion WebSocket pour l'affichage en temps réel).

## 🚀 Fonctionnalités
*   Récupération de la température en direct.
*   Script d'extraction automatique des emplois du temps.
*   Serveur API REST pour la gestion et l'affichage.
