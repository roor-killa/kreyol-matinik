# Contrats d'API — Lang Matinitjé

**Version :** v1
**Base URL :** `http://localhost:8000/api/v1`
**Format :** JSON (UTF-8)
**Authentification :** Bearer token Laravel Sanctum (endpoints marqués 🔒)

---

## Conventions

| Élément | Convention |
|---|---|
| Succès | HTTP 200 / 201 |
| Ressource introuvable | HTTP 404 `{ "detail": "..." }` |
| Erreur validation | HTTP 422 `{ "detail": [...] }` |
| Non authentifié | HTTP 401 |
| Pagination | `page` (défaut 1), `limit` (défaut 20, max 100) |
| Codes langue | `fr` = français, `crm` = créole martiniquais |

---

## 1. Dictionnaire

### `GET /dictionary/search`

Recherche un terme dans le dictionnaire.

**Paramètres query :**

| Paramètre | Type | Requis | Description |
|---|---|---|---|
| `q` | string | ✅ | Terme à rechercher |
| `lang` | `fr` \| `crm` | non | Langue du terme (défaut : les deux) |
| `page` | int | non | Numéro de page (défaut : 1) |
| `limit` | int | non | Résultats par page (défaut : 20) |

**Réponse 200 :**
```json
{
  "total": 42,
  "page": 1,
  "limit": 20,
  "results": [
    {
      "id": 1,
      "mot_creole": "annou",
      "phonetique": "a.nu",
      "categorie_gram": "vèb",
      "traductions": [
        { "langue_source": "fr", "texte_source": "allons", "texte_cible": "annou" }
      ],
      "definitions": [],
      "source": "pawolotek.com",
      "valide": true
    }
  ]
}
```

---

### `GET /dictionary/{id}`

Retourne une entrée complète du dictionnaire.

**Réponse 200 :**
```json
{
  "id": 1,
  "mot_creole": "annou",
  "phonetique": "a.nu",
  "categorie_gram": "vèb",
  "traductions": [ { "langue_source": "fr", "texte_source": "allons" } ],
  "definitions": [ { "definition": "Invite à faire quelque chose ensemble", "exemple": "Annou alé !" } ],
  "expressions": [],
  "source_id": 1,
  "valide": true,
  "created_at": "2026-02-01T00:00:00Z"
}
```

**Réponse 404 :**
```json
{ "detail": "Mot introuvable (id=99)" }
```

---

### `GET /dictionary/random`

Retourne une entrée aléatoire (utile pour un mot du jour).

**Réponse 200 :** même format que `GET /dictionary/{id}`

---

### `POST /dictionary` 🔒

Ajoute une entrée dans le dictionnaire.

**Corps :**
```json
{
  "mot_creole": "lanmou",
  "phonetique": "la.mu",
  "categorie_gram": "nom",
  "source_id": 1
}
```

**Réponse 201 :** entrée créée (même format que `GET /dictionary/{id}`)

---

### `PUT /dictionary/{id}` 🔒

Modifie une entrée existante.

**Corps :** mêmes champs que `POST`, tous optionnels.

**Réponse 200 :** entrée mise à jour.

---

## 2. Traduction

### `POST /translate`

Traduit un texte entre français et créole martiniquais.

**Corps :**
```json
{
  "text": "Allons à la mer",
  "source": "fr",
  "target": "crm"
}
```

**Réponse 200 :**
```json
{
  "source": "fr",
  "target": "crm",
  "input": "Allons à la mer",
  "output": "Annou alé bò lanmè",
  "confidence": 0.87,
  "method": "corpus_match"
}
```

> `method` : `"corpus_match"` (recherche dans le corpus) ou `"model"` (modèle Fèfèn).

---

### `GET /expressions`

Liste les expressions et proverbes créoles.

**Paramètres query :**

| Paramètre | Type | Description |
|---|---|---|
| `type` | `proverbe` \| `expression` \| `locution` | Filtre par type |
| `page` | int | Pagination |
| `limit` | int | Résultats par page |

**Réponse 200 :**
```json
{
  "total": 15,
  "results": [
    {
      "id": 1,
      "texte_creole": "Chak chen ni jou pa li",
      "texte_fr": "Chaque chien a son jour",
      "type": "proverbe",
      "source": "pawolotek.com"
    }
  ]
}
```

---

### `GET /corpus`

Accède au corpus de phrases pour l'entraînement IA.

**Paramètres query :**

| Paramètre | Type | Description |
|---|---|---|
| `domaine` | string | Filtre par domaine (quotidien, culture, nature…) |
| `limit` | int | Nombre de phrases (défaut : 50, max : 500) |
| `lang` | `crm` \| `fr` \| `both` | Filtre par langue présente |

**Réponse 200 :**
```json
{
  "total": 625,
  "results": [
    {
      "id": 1,
      "texte_creole": "Annou voyé kreyòl douvan douvan",
      "texte_fr": null,
      "domaine": "culture",
      "source": "potomitan.info"
    }
  ]
}
```

---

## 3. Médias

### `GET /media`

Liste les fichiers audio et vidéo.

**Paramètres query :**

| Paramètre | Type | Description |
|---|---|---|
| `type` | `audio` \| `video` | Filtre par type |
| `page` | int | Pagination |
| `limit` | int | Résultats par page |

**Réponse 200 :**
```json
{
  "total": 0,
  "results": [
    {
      "id": 1,
      "url": "https://pawolotek.com/.../episode.mp3",
      "type": "audio",
      "titre": "Annou palé — épisode 12",
      "duree_sec": 183,
      "source": "pawolotek.com"
    }
  ]
}
```

---

### `GET /media/{id}`

Retourne les métadonnées d'un média.

**Réponse 200 :** même format qu'un élément de `GET /media`.

---

## 4. Chatbot Fèfèn

### `POST /chat`

Envoie un message au chatbot Fèfèn et reçoit une réponse en créole.

**Corps :**
```json
{
  "message": "Saw fè ?",
  "session_id": "sess_abc123"
}
```

**Réponse 200 :**
```json
{
  "reply": "Mwen ka tchenbé ! Yo ka krié mwen Fèfèn ! é ou mèm, say i di a ?",
  "session_id": "sess_abc123",
  "model_version": "fefèn-0.1"
}
```

> `session_id` : généré automatiquement si absent, permet de maintenir le contexte de la conversation.

---

## 5. Authentification

L'authentification est gérée par **Laravel Sanctum**. FastAPI valide les tokens via un middleware dédié.

### Obtenir un token

Via Laravel : `POST /auth/login` (voir interface web).

### Utiliser le token

```
Authorization: Bearer <token>
```

### `GET /me` 🔒

Retourne le profil du contributeur connecté.

**Réponse 200 :**
```json
{
  "id": 1,
  "pseudo": "roor",
  "nb_contrib": 12,
  "created_at": "2026-02-01T00:00:00Z"
}
```

---

## 6. Codes d'erreur

| Code | Signification |
|---|---|
| 200 | Succès |
| 201 | Ressource créée |
| 400 | Requête invalide |
| 401 | Non authentifié |
| 403 | Accès refusé |
| 404 | Ressource introuvable |
| 422 | Erreur de validation des données |
| 500 | Erreur serveur interne |
