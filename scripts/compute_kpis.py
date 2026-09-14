import csv, json, math, time

# -- Assumptions, stated explicitly (per this course's standing discipline: a
# number without its source/status is not trustworthy) --
TONNES_PER_1000_RESIDENTS_PER_YEAR = 50   # ILLUSTRATIVE PROXY, not a researched
                                            # logistics statistic -- see manual.
CO2_FACTOR_KG_PER_TONNE_KM = 0.10          # within the commonly-cited range for
                                            # French/European loaded-HGV road freight
                                            # (~0.047-0.12 kg CO2e/tonne-km depending
                                            # on load factor and source) -- verify
                                            # against ADEME's current Base Empreinte
                                            # figure before citing professionally.
COST_PER_TONNE_KM_EUR = 0.12               # ILLUSTRATIVE assumption, not sourced --
                                            # real transport cost is commercial/
                                            # variable, no single authoritative figure.
STORAGE_COST_PER_TONNE_YEAR_EUR = 40       # ILLUSTRATIVE assumption.

BASELINE_WAREHOUSES = ["Paris", "Lyon", "Lille"]
SCENARIOS = {
    "baseline (Paris, Lyon, Lille)": ["Paris", "Lyon", "Lille"],
    "+ Bordeaux": ["Paris", "Lyon", "Lille", "Bordeaux"],
    "+ Marseille": ["Paris", "Lyon", "Lille", "Marseille"],
    "- Lille (close it)": ["Paris", "Lyon"],
}

def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

def load_cities(path="data/cities.csv"):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["lat"] = float(r["lat"])
        r["lon"] = float(r["lon"])
        r["population"] = int(r["population"])
        r["demand_tonnes"] = round(r["population"] / 1000 * TONNES_PER_1000_RESIDENTS_PER_YEAR, 1)
    return rows

def nearest_warehouse(city, warehouse_cities):
    best_wh, best_dist = None, None
    for wh in warehouse_cities:
        d = haversine_km(city["lat"], city["lon"], wh["lat"], wh["lon"])
        if best_dist is None or d < best_dist:
            best_dist, best_wh = d, wh["city"]
    return best_wh, round(best_dist, 1)

def assign_all(cities, warehouse_names):
    warehouse_cities = [c for c in cities if c["city"] in warehouse_names]
    links = []
    for c in cities:
        wh, dist = nearest_warehouse(c, warehouse_cities)
        links.append({**c, "assigned_warehouse": wh, "distance_km": dist})
    return links

def compute_co2(links):
    for l in links:
        l["co2_kg"] = round(l["distance_km"] * l["demand_tonnes"] * CO2_FACTOR_KG_PER_TONNE_KM, 1)
    by_warehouse = {}
    for l in links:
        by_warehouse.setdefault(l["assigned_warehouse"], {"co2_kg": 0.0, "tonnes": 0.0})
        by_warehouse[l["assigned_warehouse"]]["co2_kg"] += l["co2_kg"]
        by_warehouse[l["assigned_warehouse"]]["tonnes"] += l["demand_tonnes"]
    warehouse_summary = [
        {"warehouse": wh, "total_co2_kg": round(v["co2_kg"], 0),
         "co2_kg_per_tonne": round(v["co2_kg"] / v["tonnes"], 2) if v["tonnes"] else 0}
        for wh, v in by_warehouse.items()
    ]
    top_links = sorted(links, key=lambda l: l["co2_kg"], reverse=True)[:10]
    total_co2 = sum(l["co2_kg"] for l in links)
    total_tonnes = sum(l["demand_tonnes"] for l in links)
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "assumptions": {
            "co2_factor_kg_per_tonne_km": CO2_FACTOR_KG_PER_TONNE_KM,
            "tonnes_per_1000_residents_per_year": TONNES_PER_1000_RESIDENTS_PER_YEAR,
        },
        "total_co2_kg": round(total_co2, 0),
        "co2_kg_per_tonne_network_avg": round(total_co2 / total_tonnes, 2) if total_tonnes else 0,
        "by_warehouse": warehouse_summary,
        "top_links": [
            {"city": l["city"], "warehouse": l["assigned_warehouse"],
             "distance_km": l["distance_km"], "co2_kg": l["co2_kg"]}
            for l in top_links
        ],
        "all_cities": [
            {"city": l["city"], "lat": l["lat"], "lon": l["lon"],
             "warehouse": l["assigned_warehouse"], "co2_kg": l["co2_kg"]}
            for l in links
        ],
    }

def compute_cost(links):
    for l in links:
        l["transport_cost_eur"] = round(l["distance_km"] * l["demand_tonnes"] * COST_PER_TONNE_KM_EUR, 0)
    by_warehouse = {}
    for l in links:
        by_warehouse.setdefault(l["assigned_warehouse"], {"transport_cost_eur": 0.0, "tonnes": 0.0})
        by_warehouse[l["assigned_warehouse"]]["transport_cost_eur"] += l["transport_cost_eur"]
        by_warehouse[l["assigned_warehouse"]]["tonnes"] += l["demand_tonnes"]
    warehouse_summary = []
    for wh, v in by_warehouse.items():
        storage_cost = round(v["tonnes"] * STORAGE_COST_PER_TONNE_YEAR_EUR, 0)
        warehouse_summary.append({
            "warehouse": wh,
            "transport_cost_eur": round(v["transport_cost_eur"], 0),
            "storage_cost_eur": storage_cost,
            "total_cost_eur": round(v["transport_cost_eur"] + storage_cost, 0),
            "cost_eur_per_tonne": round((v["transport_cost_eur"] + storage_cost) / v["tonnes"], 2) if v["tonnes"] else 0,
        })
    warehouse_summary.sort(key=lambda w: w["total_cost_eur"], reverse=True)
    top_links = sorted(links, key=lambda l: l["transport_cost_eur"], reverse=True)[:10]
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "assumptions": {
            "cost_eur_per_tonne_km": COST_PER_TONNE_KM_EUR,
            "storage_cost_eur_per_tonne_year": STORAGE_COST_PER_TONNE_YEAR_EUR,
        },
        "by_warehouse": warehouse_summary,
        "top_links": [
            {"city": l["city"], "warehouse": l["assigned_warehouse"],
             "distance_km": l["distance_km"], "transport_cost_eur": l["transport_cost_eur"]}
            for l in top_links
        ],
    }

def compute_network_scenarios(cities):
    total_population = sum(c["population"] for c in cities)
    results = []
    scenario_links = {}
    for name, warehouses in SCENARIOS.items():
        links = assign_all(cities, warehouses)
        scenario_links[name] = links
        weighted_distance = sum(l["population"] * l["distance_km"] for l in links)
        avg_km_per_resident_weighted = weighted_distance / total_population
        results.append({
            "scenario": name,
            "n_warehouses": len(warehouses),
            "warehouses": warehouses,
            "avg_distance_km_population_weighted": round(avg_km_per_resident_weighted, 2),
            "max_city_distance_km": round(max(l["distance_km"] for l in links), 1),
        })
    results.sort(key=lambda r: r["avg_distance_km_population_weighted"])
    best_non_baseline = next((r for r in results if not r["scenario"].startswith("baseline")), results[1])
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scenarios": results,
        "baseline_map": [
            {"city": l["city"], "lat": l["lat"], "lon": l["lon"], "warehouse": l["assigned_warehouse"]}
            for l in scenario_links["baseline (Paris, Lyon, Lille)"]
        ],
        "best_alternative_map": [
            {"city": l["city"], "lat": l["lat"], "lon": l["lon"], "warehouse": l["assigned_warehouse"]}
            for l in scenario_links[best_non_baseline["scenario"]]
        ],
        "best_alternative_name": best_non_baseline["scenario"],
    }

def main():
    cities = load_cities()
    baseline_links = assign_all(cities, BASELINE_WAREHOUSES)

    co2 = compute_co2(baseline_links)
    cost = compute_cost(baseline_links)
    network = compute_network_scenarios(cities)

    print("=== CO2 (baseline network) ===")
    print(f"Total network CO2: {co2['total_co2_kg']:.0f} kg/year")
    print(f"Network avg CO2/tonne: {co2['co2_kg_per_tonne_network_avg']} kg/tonne")
    for w in co2["by_warehouse"]:
        print(f"  {w['warehouse']}: {w['total_co2_kg']:.0f} kg, {w['co2_kg_per_tonne']} kg/tonne")

    print("\n=== Cost (baseline network) ===")
    for w in cost["by_warehouse"]:
        print(f"  {w['warehouse']}: transport {w['transport_cost_eur']:.0f} EUR + storage "
              f"{w['storage_cost_eur']:.0f} EUR = {w['total_cost_eur']:.0f} EUR "
              f"({w['cost_eur_per_tonne']} EUR/tonne)")

    print("\n=== Network scenarios (population-weighted avg distance) ===")
    for s in network["scenarios"]:
        print(f"  {s['scenario']}: {s['avg_distance_km_population_weighted']} km avg "
              f"(worst city: {s['max_city_distance_km']} km), {s['n_warehouses']} warehouses")
    print(f"Best-performing alternative: {network['best_alternative_name']}")

    with open("docs/data/co2.json", "w") as f:
        json.dump(co2, f, indent=2)
    with open("docs/data/cost.json", "w") as f:
        json.dump(cost, f, indent=2)
    with open("docs/data/network.json", "w") as f:
        json.dump(network, f, indent=2)
    print("\nWrote docs/data/co2.json, cost.json, network.json")

if __name__ == "__main__":
    main()
