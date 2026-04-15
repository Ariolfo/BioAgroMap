from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import re
import requests
import pandas as pd
import os
from shapely import from_wkt


# --- Parámetros de usuario ---
copernicus_user = "agrosaviatest@gmail.com"
copernicus_password = "Geo@gro20255"
data_collection = "SENTINEL-1"

# --- Configuración de la ubicación en formato WKT  extraidas de https://geojson.io/ ---
AREA_WKT = "POLYGON ((-75.54849415112218 6.22786994060958, -75.54849415112218 6.206209342881479, -75.5174451940831 6.206209342881479, -75.5174451940831 6.22786994060958, -75.54849415112218 6.22786994060958))"

# --- Directorio con carpetas S2 (se leen las fechas de los nombres) ---
S2_DOWNLOAD_DIR = "downloads_sentinel2"

# --- Directorio de descarga S1 ---
DOWNLOAD_DIR = "downloads_sentinel1"

def validate_wkt_polygon(wkt_string):
    """
    Valida que el string WKT sea un polígono válido
    """
    try:
        geom = from_wkt(wkt_string)
        if geom.geom_type != 'Polygon':
            raise ValueError(f"La geometría debe ser un POLYGON, encontrado: {geom.geom_type}")
        if not geom.is_valid:
            raise ValueError("El polígono WKT no es válido")
        return True
    except ImportError:
        # Si shapely no está disponible, hacer validación básica
        if not wkt_string.strip().upper().startswith('POLYGON'):
            raise ValueError("El WKT debe comenzar con 'POLYGON'")
        if wkt_string.count('(') != wkt_string.count(')'):
            raise ValueError("Paréntesis desbalanceados en el WKT")
        return True
    except Exception as e:
        raise ValueError(f"Error validando WKT: {e}")

# Esta funcion es solo informativa y no influye en el proceso de descarga
def extract_bounds_from_wkt(wkt_string):
    """
    Extrae los límites (bounds) de un polígono WKT para mostrar información
    """
    try:
        geom = from_wkt(wkt_string)
        bounds = geom.bounds  # (minx, miny, maxx, maxy)
        return bounds
    except ImportError:
        # Parsing básico si shapely no está disponible
        coords_str = wkt_string.upper().replace('POLYGON', '').strip()
        coords_str = coords_str.strip('()')
        if ',,' in coords_str:
            coords_str = coords_str.split(',,')[0]  # Tomar solo el anillo exterior
        
        # Extraer coordenadas
        pairs = coords_str.split(',')
        lons, lats = [], []
        for pair in pairs:
            parts = pair.strip().split()
            if len(parts) >= 2:
                try:
                    lons.append(float(parts[0]))
                    lats.append(float(parts[1]))
                except ValueError:
                    continue
        
        if lons and lats:
            return (min(lons), min(lats), max(lons), max(lats))
        else:
            return None


def get_s2_dates_from_folders(s2_dir: str) -> list[date]:
    """
    Escanea el directorio de Sentinel-2 y extrae las fechas de adquisición
    desde los nombres de carpeta (ej. S2A_MSIL2A_20230828T151711_... -> 2023-08-28).
    Devuelve lista de fechas ordenadas y sin duplicados.
    """
    if not os.path.isdir(s2_dir):
        return []
    # Patrón: S2A_MSIL2A_YYYYMMDD o S2A_MSIL1C_YYYYMMDD
    pattern = re.compile(r"S2[AB]_MSIL[12][AC]_(\d{4})(\d{2})(\d{2})T", re.IGNORECASE)
    dates_found = []
    for name in os.listdir(s2_dir):
        full_path = os.path.join(s2_dir, name)
        if not os.path.isdir(full_path):
            continue
        match = pattern.search(name)
        if match:
            y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
            try:
                dates_found.append(date(y, m, d))
            except ValueError:
                continue
    return sorted(set(dates_found))


def get_s1_products_with_dates(s1_dir: str) -> list[tuple[date, str]]:
    """
    Escanea el directorio de Sentinel-1 y devuelve lista de (fecha, nombre)
    a partir de nombres de carpeta .SAFE o archivo .zip (ej. ..._20230829T... -> 2023-08-29).
    """
    if not os.path.isdir(s1_dir):
        return []
    pattern = re.compile(r"S1[AB]_IW_GRDH_[^_]+_(\d{4})(\d{2})(\d{2})T", re.IGNORECASE)
    out = []
    for name in os.listdir(s1_dir):
        full = os.path.join(s1_dir, name)
        if not (os.path.isdir(full) or name.endswith(".zip")):
            continue
        if not (".SAFE" in name or name.endswith(".zip")):
            continue
        match = pattern.search(name)
        if match:
            y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
            try:
                out.append((date(y, m, d), name))
            except ValueError:
                pass
    return sorted(out, key=lambda x: x[0])


def verify_s1_s2_correspondence(s2_dir: str = None, s1_dir: str = None):
    """
    Verifica qué productos S1 corresponden a cada S2 (por cercanía de fecha)
    e imprime una tabla: S2 fecha, S2 nombre, S1 fecha, S1 nombre, Δ días.
    """
    s2_dir = s2_dir or S2_DOWNLOAD_DIR
    s1_dir = s1_dir or DOWNLOAD_DIR

    s2_dates = get_s2_dates_from_folders(s2_dir)
    s2_folders = []
    pattern_s2 = re.compile(r"S2[AB]_MSIL[12][AC]_(\d{4})(\d{2})(\d{2})T", re.IGNORECASE)
    if os.path.isdir(s2_dir):
        for name in sorted(os.listdir(s2_dir)):
            full = os.path.join(s2_dir, name)
            if not os.path.isdir(full):
                continue
            m = pattern_s2.search(name)
            if m:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                try:
                    s2_folders.append((date(y, mo, d), name))
                except ValueError:
                    pass
    s2_folders.sort(key=lambda x: x[0])

    s1_list = get_s1_products_with_dates(s1_dir)
    if not s1_list:
        print(f"No hay productos S1 en '{s1_dir}'.")
        return

    s1_dates = [d for d, _ in s1_list]

    print("=" * 100)
    print("CORRESPONDENCIA SENTINEL-2 ↔ SENTINEL-1 (por fecha más cercana)")
    print("=" * 100)
    print(f"{'S2 fecha':<12} {'Δ días':>6} {'S1 fecha':<12} {'S2 carpeta':<55} {'S1 producto'}")
    print("-" * 100)

    for s2_date, s2_name in s2_folders:
        # S1 más cercano en fecha
        deltas = [(abs((s1_d - s2_date).days), s1_d) for s1_d in s1_dates]
        delta_days, best_s1_date = min(deltas, key=lambda x: x[0])
        # Nombre del producto S1 para esa fecha (puede haber más de uno el mismo día)
        s1_names = [n for d, n in s1_list if d == best_s1_date]
        s1_display = s1_names[0] if s1_names else "—"
        if len(s1_names) > 1:
            s1_display += f" (+{len(s1_names)-1} más)"

        s2_short = s2_name[:52] + "…" if len(s2_name) > 55 else s2_name
        s1_short = s1_display[:45] + "…" if len(s1_display) > 48 else s1_display
        print(f"{s2_date!s:<12} {delta_days:>+6} {best_s1_date!s:<12} {s2_short:<55} {s1_short}")

    print("-" * 100)
    print(f"S2: {len(s2_folders)} escenas  |  S1 en disco: {len(s1_list)} productos")
    print("=" * 100)


def get_keycloak_token(username: str, password: str) -> str:
    """
    Obtiene token de autenticación de Copernicus
    """
    data = {
        "client_id": "cdse-public",
        "username": username,
        "password": password,
        "grant_type": "password",
    }
    r = requests.post(
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        data=data,
    )
    r.raise_for_status()
    return r.json()["access_token"]

def download_product(product_id, product_name, session, output_dir):
    """
    Descarga un producto específico de Copernicus
    """
    print(f"  → Descargando: {product_name}")
    
    # URL de descarga
    url = f"https://catalogue.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"
    
    # Hacer la petición
    r1 = session.get(url, allow_redirects=False)
    download_url = r1.headers.get("Location", url)
    
    r2 = session.get(download_url, allow_redirects=True,
                     headers={"Authorization": session.headers["Authorization"]},
                     stream=True)
    r2.raise_for_status()
    
    # Guardar archivo
    zip_path = os.path.join(output_dir, f"{product_name}.zip")
    
    with open(zip_path, "wb") as f:
        total_size = 0
        for chunk in r2.iter_content(chunk_size=8192):
            f.write(chunk)
            total_size += len(chunk)
            
            # Mostrar progreso cada 100MB
            if total_size % (100 * 1024 * 1024) == 0:
                print(f"    Descargado: {total_size // (1024*1024)} MB")
    
    file_size_mb = total_size // (1024*1024)
    print(f"  ✅ Completado: {product_name} ({file_size_mb} MB)")
    
    return zip_path


def search_and_download_for_dates(wkt_polygon, dates_list, output_dir):
    """
    Busca y descarga productos Sentinel-1 para cada fecha en dates_list
    (fechas extraídas de las carpetas S2). Para cada fecha busca S1 en una
    ventana de ±2 días y descarga el producto más cercano.
    """
    validate_wkt_polygon(wkt_polygon)
    os.makedirs(output_dir, exist_ok=True)

    total_downloaded = 0
    total_size_mb = 0

    for acq_date in dates_list:
        window_start = acq_date - timedelta(days=2)
        window_end = acq_date + timedelta(days=3)
        start_str = window_start.strftime("%Y-%m-%d")
        end_str = window_end.strftime("%Y-%m-%d")

        print(f"\n{'='*60}")
        print(f"S2 fecha: {acq_date} → Buscando S1 en ventana {start_str} .. {end_str}")
        print(f"{'='*60}")

        token = get_keycloak_token(copernicus_user, copernicus_password)
        session = requests.Session()
        session.verify = False
        session.headers.update({"Authorization": f"Bearer {token}"})

        query_url = (
            "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
            f"?$filter=Collection/Name eq '{data_collection}'"
            f" and OData.CSC.Intersects(area=geography'SRID=4326;{wkt_polygon}')"
            f" and ContentDate/Start ge {start_str}T00:00:00.000Z"
            f" and ContentDate/Start lt {end_str}T00:00:00.000Z"
            "&$count=True&$top=1000"
        )

        try:
            resp = session.get(query_url)
            resp.raise_for_status()
            j = resp.json()
            total_products = j.get('@odata.count', 0)
            print(f"Productos S1 en ventana: {total_products}")

            if 'value' in j and j['value']:
                df = pd.DataFrame.from_dict(j["value"])
                df["startDate"] = pd.to_datetime(
                    df["ContentDate"].apply(lambda cd: cd["Start"])
                )
                df_filtered = df[df["Name"].str.startswith("S1A_IW_GRDH")]
                print(f"Productos S1A_IW_GRDH: {len(df_filtered)}")

                if not df_filtered.empty:
                    # Ordenar por cercanía a acq_date y tomar el más cercano
                    df_filtered = df_filtered.copy()
                    df_filtered["date_diff"] = abs(
                        df_filtered["startDate"].dt.date - acq_date
                    )
                    df_sorted = df_filtered.sort_values("date_diff")
                    first_product = df_sorted.iloc[0]

                    prod_id = first_product["Id"]
                    identifier = first_product["Name"].split(".")[0]
                    product_date = first_product["startDate"].strftime("%Y-%m-%d")

                    print(f"Seleccionado: {identifier} ({product_date})")

                    expected_file = os.path.join(output_dir, f"{identifier}.zip")
                    if os.path.exists(expected_file):
                        file_size = os.path.getsize(expected_file) // (1024 * 1024)
                        print(f"  ⚠️  Ya existe: {identifier}.zip ({file_size} MB)")
                        total_size_mb += file_size
                    else:
                        zip_path = download_product(
                            prod_id, identifier, session, output_dir
                        )
                        if os.path.exists(zip_path):
                            file_size = os.path.getsize(zip_path) // (1024 * 1024)
                            total_downloaded += 1
                            total_size_mb += file_size
                else:
                    print("  ❌ No hay productos S1A_IW_GRDH en esta ventana")
            else:
                print("  ❌ No se encontraron productos S1 en esta ventana")

        except requests.HTTPError as e:
            print(f"  ❌ Error HTTP: {e}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    # Resumen final
    print(f"\n{'='*60}")
    print("RESUMEN DE DESCARGA SENTINEL-1 (por fechas S2)")
    print(f"{'='*60}")
    print(f"Productos descargados: {total_downloaded}")
    print(f"Tamaño total: {total_size_mb:,} MB ({total_size_mb/1024:.1f} GB)")
    print(f"Directorio: {output_dir}")
    if os.path.exists(output_dir):
        files = [f for f in os.listdir(output_dir) if f.endswith('.zip')]
        if files:
            print("\nArchivos SAR en directorio:")
            for i, f in enumerate(sorted(files), 1):
                fp = os.path.join(output_dir, f)
                sz = os.path.getsize(fp) // (1024 * 1024)
                print(f"  {i:2d}. {f} ({sz} MB)")
    return total_downloaded, total_size_mb


def search_and_download_monthly(wkt_polygon, start_date, end_date, output_dir):
    """
    Busca y descarga productos Sentinel-1 mes por mes usando WKT
    """
    # Validar WKT
    validate_wkt_polygon(wkt_polygon)
    
    print(f"Área de búsqueda (WKT): {wkt_polygon}")
    
    # Extraer bounds para mostrar información
    bounds = extract_bounds_from_wkt(wkt_polygon)
    if bounds:
        min_lon, min_lat, max_lon, max_lat = bounds
        width = max_lon - min_lon
        height = max_lat - min_lat
        print(f"Límites del área: {min_lon:.3f}, {min_lat:.3f} → {max_lon:.3f}, {max_lat:.3f}")
        print(f"Dimensiones: {width:.3f}° × {height:.3f}°")
    
    print(f"Período: {start_date} a {end_date}")
    
    # Crear directorio de salida
    os.makedirs(output_dir, exist_ok=True)
    
    # Contadores
    total_downloaded = 0
    total_size_mb = 0
    
    # Procesar mes por mes
    current = start_date
    while current < end_date:
        next_month = current + relativedelta(months=1)
        start_str = current.strftime("%Y-%m-%d")
        end_str = next_month.strftime("%Y-%m-%d")
        
        print(f"\n{'='*60}")
        print(f"PROCESANDO: {start_str} → {end_str}")
        print(f"{'='*60}")
        
        # Obtener token fresco para cada mes
        token = get_keycloak_token(copernicus_user, copernicus_password)
        session = requests.Session()
        session.verify = False
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Construir consulta al catálogo usando el WKT directamente
        query_url = (
            "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
            f"?$filter=Collection/Name eq '{data_collection}'"
            f" and OData.CSC.Intersects(area=geography'SRID=4326;{wkt_polygon}')"
            f" and ContentDate/Start ge {start_str}T00:00:00.000Z"
            f" and ContentDate/Start lt {end_str}T00:00:00.000Z"
            "&$count=True&$top=1000"
        )
        
        print(f"Consultando catálogo...")
        
        try:
            resp = session.get(query_url)
            resp.raise_for_status()
            
            j = resp.json()
            total_products = j.get('@odata.count', 0)
            
            print(f"Productos encontrados: {total_products}")
            
            if 'value' in j and j['value']:
                df = pd.DataFrame.from_dict(j["value"])
                
                # Convertir fechas
                df["startDate"] = pd.to_datetime(
                    df["ContentDate"].apply(lambda cd: cd["Start"])
                )
                
                # Filtrar por S1A SAR datos procesados
                # Otras opciones son: S1A_IW_GRDH, S1A_IW_SLC, S1A_EW_GRDH
                df_filtered = df[df["Name"].str.startswith("S1A_IW_GRDH")]
                
                print(f"Productos S1A SAR válidos: {len(df_filtered)}")
                
                if not df_filtered.empty:
                    # Ordenar por fecha y tomar el primero
                    df_sorted = df_filtered.sort_values('startDate')
                    first_product = df_sorted.iloc[0]
                    
                    prod_id = first_product["Id"]
                    identifier = first_product["Name"].split(".")[0]
                    product_date = first_product["startDate"].strftime("%Y-%m-%d")
                    
                    print(f"Seleccionado: {identifier} ({product_date})")
                    
                    # Verificar si ya existe
                    expected_file = os.path.join(output_dir, f"{identifier}.zip")
                    if os.path.exists(expected_file):
                        file_size = os.path.getsize(expected_file) // (1024*1024)
                        print(f"  ⚠️  Archivo ya existe: {identifier}.zip ({file_size} MB)")
                        print(f"  🔄 Saltando descarga...")
                        # Contar size descargado
                        total_size_mb += file_size
                    else:
                        # Descargar
                        zip_path = download_product(prod_id, identifier, session, output_dir)
                        
                        # Actualizar contadores
                        if os.path.exists(zip_path):
                            file_size = os.path.getsize(zip_path) // (1024*1024)
                            total_downloaded += 1
                            total_size_mb += file_size
                        
                else:
                    print("  ❌ No hay productos S1A SAR válidos para este mes")
                    
            else:
                print("  ❌ No se encontraron productos para este mes")
                
        except requests.HTTPError as e:
            print(f"  ❌ Error HTTP al consultar catálogo: {e}")
        except Exception as e:
            print(f"  ❌ Error inesperado: {e}")
        
        # Avanzar al siguiente mes
        current = next_month
        
# Resumen final
    print(f"\n{'='*60}")
    print("RESUMEN DE DESCARGA SENTINEL-1")
    print(f"{'='*60}")
    print(f"Productos descargados: {total_downloaded}")
    print(f"Tamaño total: {total_size_mb:,} MB ({total_size_mb/1024:.1f} GB)")
    print(f"Directorio: {output_dir}")
    
    # Listar archivos descargados
    if os.path.exists(output_dir):
        files = [f for f in os.listdir(output_dir) if f.endswith('.zip')]
        if files:
            print(f"\nArchivos SAR en directorio:")
            for i, file in enumerate(sorted(files), 1):
                file_path = os.path.join(output_dir, file)
                file_size = os.path.getsize(file_path) // (1024*1024)
                print(f"  {i:2d}. {file} ({file_size} MB)")
    
    return total_downloaded, total_size_mb

def main():
    """
    Función principal: lee las fechas de las carpetas S2 en S2_DOWNLOAD_DIR
    y descarga Sentinel-1 para esas mismas fechas (misma área WKT).
    """
    print("="*80)
    print("DESCARGA SENTINEL-1 SAR (fechas según carpetas S2)")
    print("="*80)

    # Fechas desde nombres de carpetas S2
    dates_s2 = get_s2_dates_from_folders(S2_DOWNLOAD_DIR)
    if not dates_s2:
        print(f"No se encontraron carpetas S2 en '{S2_DOWNLOAD_DIR}'.")
        print("Revisa que existan carpetas tipo S2A_MSIL2A_YYYYMMDD...SAFE")
        return

    print(f"Carpetas S2 escaneadas: {S2_DOWNLOAD_DIR}")
    print(f"Fechas de adquisición S2: {[d.isoformat() for d in dates_s2]}")
    print(f"Área (WKT): {AREA_WKT}")

    bounds = extract_bounds_from_wkt(AREA_WKT)
    if bounds:
        min_lon, min_lat, max_lon, max_lat = bounds
        w, h = max_lon - min_lon, max_lat - min_lat
        print(f"Límites: {min_lon:.3f}, {min_lat:.3f} → {max_lon:.3f}, {max_lat:.3f} ({w:.3f}° × {h:.3f}°)")
    print(f"Directorio S1: {DOWNLOAD_DIR}")
    print(f"Producto: S1A_IW_GRDH (SAR Ground Range Detected)")
    print("="*80)

    total_files, total_size = search_and_download_for_dates(
        AREA_WKT, dates_s2, DOWNLOAD_DIR
    )

    print(f"\n🎉 PROCESO COMPLETADO")
    print(f"   Total archivos SAR: {total_files}")
    print(f"   Tamaño total: {total_size:,} MB")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("verify", "--verify", "-v"):
        verify_s1_s2_correspondence()
    else:
        main()