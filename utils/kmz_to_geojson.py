#!/usr/bin/env python3
"""
Utilitário de Conversão Automatizada KMZ/KML -> GeoJSON para Provedores de Internet (ISPs).

Suporta:
1. Descompactação direta de arquivos KMZ (KML compactado em ZIP).
2. Extração de geometrias (Polygon, MultiGeometry) e atributos (Placemarks, nomes, descrições).
3. Conversão para o formato GeoJSON padrão RFC 7946.
4. Processamento individual de arquivo ou lote de uma pasta inteira.

Instruções com GDAL / ogr2ogr (Alternativa nativa C++):
-------------------------------------------------------
Para converter via terminal usando GDAL (disponível em Linux/Docker ou OSGeo4W no Windows):
  ogr2ogr -f "GeoJSON" output.geojson "/vsizip/input.kmz/doc.kml" -t_srs EPSG:4326

Uso deste script Python (Puro / Zero dependências binárias C++):
----------------------------------------------------------------
  python kmz_to_geojson.py entrada.kmz saida.geojson --tech "Fibra GPON"
  python kmz_to_geojson.py ./pasta_kmz/ ./pasta_geojson/ --batch --tech "Rede Neutra"
"""

import os
import sys
import json
import zipfile
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List

def parse_kml_coordinates(coord_text: str) -> List[List[float]]:
    """Converte a string de coordenadas do KML em lista de pares [lon, lat], tolerando espaços arbitrários."""
    import re
    coords = []
    clean_text = re.sub(r"\s*,\s*", ",", coord_text.strip())
    tokens = clean_text.split()
    for token in tokens:
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                coords.append([lon, lat])
            except ValueError:
                continue
    return coords

def convert_kml_to_geojson(kml_content: str, layer_name: str = "Camada de Cobertura", technology: str = "Fibra GPON") -> Dict[str, Any]:
    """Converte o XML KML em um dicionário FeatureCollection GeoJSON."""
    root = ET.fromstring(kml_content)

    # Remover prefixos de namespace de todas as tags da árvore para busca universal
    for elem in root.iter():
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]

    def find_all(element, tag):
        return element.findall(f".//{tag}")

    def find_one(element, tag):
        return element.find(f".//{tag}")

    placemarks = find_all(root, "Placemark")
    features = []

    for idx, pm in enumerate(placemarks):
        name_el = find_one(pm, "name")
        desc_el = find_one(pm, "description")
        
        pm_name = name_el.text.strip() if name_el is not None and name_el.text else f"Mancha-{idx + 1}"
        pm_desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

        polygons = find_all(pm, "Polygon")
        for poly in polygons:
            outer = find_one(poly, "outerBoundaryIs")
            if outer is None:
                continue
            coord_el = find_one(outer, "coordinates")
            if coord_el is None or not coord_el.text:
                continue

            ring = parse_kml_coordinates(coord_el.text)
            if len(ring) >= 3:
                # Fechar anel se necessário
                if ring[0] != ring[-1]:
                    ring.append(ring[0])

                feature = {
                    "type": "Feature",
                    "properties": {
                        "id": f"poly_{idx + 1}",
                        "name": pm_name,
                        "description": pm_desc,
                        "region": pm_name,
                        "pop": "POP Central",
                        "technology": technology,
                        "origem": "KMZ_Import"
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [ring]
                    }
                }
                features.append(feature)

    return {
        "type": "FeatureCollection",
        "name": layer_name,
        "technology": technology,
        "features": features
    }

def convert_kmz_file(input_path: Path, output_path: Path, technology: str = "Fibra GPON"):
    """Lê um arquivo .kmz ou .kml e salva em .geojson."""
    kml_str = ""

    if input_path.suffix.lower() == ".kmz":
        with zipfile.ZipFile(input_path, 'r') as z:
            kml_files = [name for name in z.namelist() if name.lower().endswith(".kml")]
            if not kml_files:
                raise ValueError(f"Nenhum arquivo .kml encontrado dentro de {input_path}")
            # Pegar o doc.kml principal
            with z.open(kml_files[0]) as kml_file:
                kml_str = kml_file.read().decode("utf-8", errors="ignore")
    else:
        with open(input_path, "r", encoding="utf-8", errors="ignore") as f:
            kml_str = f.read()

    geojson = convert_kml_to_geojson(kml_str, layer_name=input_path.stem, technology=technology)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as out:
        json.dump(geojson, out, ensure_ascii=False, indent=2)

    print(f"[OK] Convertido com sucesso: {input_path.name} -> {output_path.name} ({len(geojson['features'])} polígonos)")

def main():
    parser = argparse.ArgumentParser(description="Conversor de Cobertura KMZ/KML para GeoJSON (ISP Viabilidade)")
    parser.add_argument("input", help="Caminho do arquivo KMZ/KML ou pasta de entrada")
    parser.add_argument("output", help="Caminho do arquivo GeoJSON de saída ou pasta de saída")
    parser.add_argument("--tech", default="Fibra GPON", help="Tecnologia da mancha (ex: 'Fibra GPON', 'Rede Neutra', 'Rádio 5.8GHz')")
    parser.add_argument("--batch", action="store_true", help="Processar todos os arquivos KMZ/KML contidos na pasta de entrada")

    args = parser.parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if args.batch:
        if not input_path.is_dir():
            print(f"Erro: Para o modo --batch, a entrada '{input_path}' deve ser um diretório.")
            sys.exit(1)
        
        files = list(input_path.glob("*.kmz")) + list(input_path.glob("*.kml"))
        print(f"Iniciando conversão em lote de {len(files)} arquivos...")
        for f in files:
            dest = output_path / f"{f.stem}.geojson"
            try:
                convert_kmz_file(f, dest, technology=args.tech)
            except Exception as e:
                print(f"[ERRO] Falha ao converter {f.name}: {e}")
    else:
        convert_kmz_file(input_path, output_path, technology=args.tech)

if __name__ == "__main__":
    main()
