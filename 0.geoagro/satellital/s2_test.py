from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import requests
import pandas as pd
import os
from shapely import from_wkt

# --- Parámetros de usuario ---
copernicus_user = "agrosaviatest@gmail.com"
copernicus_password = "Geo@gro20255"
data_collection = "SENTINEL-2"

# --- Configuración de la ubicación en formato WKT extraidas de https://geojson.io/ ---
AREA_WKT = "POLYGON ((-75.54849415112218 6.22786994060958, -75.54849415112218 6.206209342881479, -75.5174451940831 6.206209342881479, -75.5174451940831 6.22786994060958, -75.54849415112218 6.22786994060958))"

# --- Configuración de fechas ---
START_DATE = date(2024, 12, 1)
END_DATE = date(2025, 1, 1)

# --- Directorio de descarga ---
DOWNLOAD_DIR = "downloads_sentinel2"

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

def search_and_download_monthly(wkt_polygon, start_date, end_date, output_dir):
    """
    Busca y descarga productos Sentinel-2 mes por mes usando WKT
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
                
                # Filtrar por S2A L1C (otra opcion es L2A)
                df_filtered = df[df["Name"].str.startswith("S2A_MSIL1C")]
                
                print(f"Productos S2A L1C válidos: {len(df_filtered)}")
                
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
                    else:
                        # Descargar
                        zip_path = download_product(prod_id, identifier, session, output_dir)
                        
                        # Actualizar contadores
                        if os.path.exists(zip_path):
                            file_size = os.path.getsize(zip_path) // (1024*1024)
                            total_downloaded += 1
                            total_size_mb += file_size
                        
                else:
                    print("  ❌ No hay productos S2A L1C válidos para este mes")
                    
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
    print("RESUMEN DE DESCARGA")
    print(f"{'='*60}")
    print(f"Productos descargados: {total_downloaded}")
    print(f"Tamaño total: {total_size_mb:,} MB ({total_size_mb/1024:.1f} GB)")
    print(f"Directorio: {output_dir}")
    
    # Listar archivos descargados
    if os.path.exists(output_dir):
        files = [f for f in os.listdir(output_dir) if f.endswith('.zip')]
        if files:
            print(f"\nArchivos en directorio:")
            for i, file in enumerate(sorted(files), 1):
                file_path = os.path.join(output_dir, file)
                file_size = os.path.getsize(file_path) // (1024*1024)
                print(f"  {i:2d}. {file} ({file_size} MB)")
    
    return total_downloaded, total_size_mb

def main():
    """
    Función principal
    """
    print("="*80)
    print("DESCARGA MENSUAL DE SENTINEL-2")
    print("="*80)
    print(f"Coordenadas: {AREA_WKT}")
    print(f"Período: {START_DATE} a {END_DATE}")
    print(f"Directorio: {DOWNLOAD_DIR}")
    print("="*80)
    
    # Ejecutar descarga
    total_files, total_size = search_and_download_monthly(
        AREA_WKT, 
        START_DATE, 
        END_DATE, 
        DOWNLOAD_DIR
    )
    
    print(f"\n🎉 PROCESO COMPLETADO")
    print(f"   Total archivos: {total_files}")
    print(f"   Tamaño total: {total_size:,} MB")

if __name__ == "__main__":
    main()