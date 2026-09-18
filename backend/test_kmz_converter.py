import sys
import zipfile
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.kmz_to_geojson import convert_kmz_file

def test_kmz_conversion():
    test_dir = Path("sample_data/temp_kmz_test")
    test_dir.mkdir(parents=True, exist_ok=True)

    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Cobertura Teste KMZ</name>
    <Placemark>
      <name>Mancha Alpha</name>
      <description>Mancha de teste GPON</description>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -46.66, -23.55, 0
              -46.65, -23.56, 0
              -46.64, -23.57, 0
              -46.66, -23.55, 0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""
    # 1. Criar um arquivo .kmz (zip contendo doc.kml)
    kmz_path = test_dir / "teste_cobertura.kmz"
    with zipfile.ZipFile(kmz_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml_content)

    # 2. Executar a conversão
    out_geojson = test_dir / "teste_cobertura.geojson"
    convert_kmz_file(kmz_path, out_geojson, technology="Fibra GPON")

    assert out_geojson.exists(), "Arquivo GeoJSON de saída deve existir"
    with open(out_geojson, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1
    feat = data["features"][0]
    assert feat["properties"]["name"] == "Mancha Alpha"
    assert feat["geometry"]["type"] == "Polygon"
    print("\n[OK] Teste de conversão KMZ -> GeoJSON passou com sucesso!")

    # Limpeza
    kmz_path.unlink()
    out_geojson.unlink()
    test_dir.rmdir()

if __name__ == "__main__":
    test_kmz_conversion()
