# Diagramme de classes — Phase 1 : Scraper Lang Matinitjé

> Rendu automatique sur GitHub. Export PNG : coller le bloc Mermaid sur [mermaid.live](https://mermaid.live)

```mermaid
classDiagram

%% ─── ABSTRACT BASE ───────────────────────────────────────────────────────────

class BaseScraper {
    <<abstract>>
    +base_url : str
    +delay : float
    +headers : dict
    +data : list[dict]
    -_observers : list[ScraperObserver]
    +attach(observer)
    +detach(observer)
    +_notify(event, payload)
    +fetch_page(url) BeautifulSoup|None
    +save_to_json(path)
    +save_to_csv(path)
    +scrape(max_pages)* list[dict]
    +parse(soup)* list[dict]
}

%% ─── CONCRETE SCRAPERS ───────────────────────────────────────────────────────

class PawoloTekScraper {
    +BASE_URL : str
    +categories : list[str]
    +source_id : int
    +scrape(max_pages) list[dict]
    +parse(soup) list[dict]
    -_scrape_rss_feed(feed_base, category, max_items)
    -_fetch_xml(url) BeautifulSoup|None
    -_parse_rss_item(item_tag) dict|None
}

class PotomitanScraper {
    +BASE_URL : str
    +sections : list[str]
    +source_id : int
    +scrape(max_pages) list[dict]
    +parse(soup) list[dict]
    -_scrape_contes(index_url, max_items)
    -_scrape_poemes(index_url, max_items)
    -_extract_conte_links(soup, base_url)
    -_extract_poeme_links(soup, base_url)
    -_parse_conte_page(soup, url) dict|None
    -_parse_poeme_page(soup, url, auteur) dict|None
}

BaseScraper <|-- PawoloTekScraper : hérite
BaseScraper <|-- PotomitanScraper : hérite

%% ─── OBSERVER PATTERN ────────────────────────────────────────────────────────

class ScraperObserver {
    <<abstract>>
    +update(event, payload)*
}

class LogObserver {
    +name : str
    +update(event, payload)
}

class StatsObserver {
    +fetches : int
    +errors : int
    +items_parsed : int
    +started_at : datetime|None
    +update(event, payload)
    +summary() dict
}

ScraperObserver <|-- LogObserver : hérite
ScraperObserver <|-- StatsObserver : hérite
BaseScraper "1" o-- "0..*" ScraperObserver : notifie

%% ─── FACTORY / MANAGER ──────────────────────────────────────────────────────

class ScraperManager {
    -_scrapers : list[BaseScraper]
    +create_scraper(source, kwargs)$ BaseScraper
    +available_sources()$ list[str]
    +add_scraper(scraper)
    +scrape_all(max_pages) dict
    +aggregate() list[dict]
}

ScraperManager "1" *-- "0..*" BaseScraper : gère

%% ─── PIPELINE ────────────────────────────────────────────────────────────────

class DataPipeline {
    +db_url : str|None
    +clean(raw_data) list[dict]
    +detect_language(text) str
    +import_to_db(processed_data) int
    -_ensure_sources(cur, data)
    -_insert_entry(cur, entry) int
    -_normalize_text_fields(entry) dict
}

ScraperManager ..> DataPipeline : fournit les données
```

## Légende des patterns

| Pattern | Classes impliquées |
|---|---|
| **Template Method** | `BaseScraper` définit le squelette ; `scrape()` et `parse()` sont abstraites |
| **Observer** | `BaseScraper` (sujet) → `ScraperObserver` (observateurs) |
| **Factory** | `ScraperManager.create_scraper()` instancie la bonne sous-classe |
| **Strategy** | Chaque scraper encapsule sa propre stratégie d'extraction |
