from pathlib import Path

import numpy as np
import rasterio
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.neighbors import KNeighborsClassifier

def cluster_image(imagery_fp, cluster_type='kmeans', n_clusters=5, visualize=True):
    """
    Realiza clustering en una imagen satelital utilizando diferentes algoritmos.
    
    Parámetros:
    imagery_fp (str): Ruta al archivo de imagen satelital (.tif)
    cluster_type (str): Tipo de clustering a utilizar ('kmeans', 'gmm', 'knn', o 'all')
    n_clusters (int): Número de clusters a generar
    visualize (bool): Si se debe visualizar el resultado
    
    Retorna:
    dict: Diccionario con las imágenes procesadas y las etiquetas
    """
    # Abrir la imagen
    img_file = rasterio.open(imagery_fp)
    img = img_file.read()
    
    # Reformar la imagen para clustering
    pixels = img.reshape(img.shape[0], img.shape[1] * img.shape[2]).T
    
    # Píxeles válidos: finitos en todos los canales (NDVI puede ser 0 legítimamente)
    mascara = np.all(np.isfinite(pixels), axis=1)
    
    # Filtrar los píxeles que no son de fondo
    pixels_filtrados = pixels[mascara]
    
    results = {}
    
    # Función para crear la imagen clusterizada
    def create_clustered_image(labels):
        clustered_image = np.full((img.shape[1], img.shape[2]), -1)  # -1 para fondo
        clustered_image[mascara.reshape(img.shape[1], img.shape[2])] = labels
        return clustered_image
    
    # Aplicar K-means si se solicita
    if cluster_type.lower() == 'kmeans' or cluster_type.lower() == 'all':
        kmeans = KMeans(n_clusters=n_clusters, random_state=0).fit(pixels_filtrados)
        labels_filtrados_kmeans = kmeans.labels_
        clustered_image_kmeans = create_clustered_image(labels_filtrados_kmeans)
        results['kmeans'] = {
            'image': clustered_image_kmeans,
            'labels': labels_filtrados_kmeans,
            'model': kmeans
        }
    
    # Aplicar Gaussian Mixture Model si se solicita
    if cluster_type.lower() == 'gmm' or cluster_type.lower() == 'all':
        gmm = GaussianMixture(n_components=n_clusters)
        gmm.fit(pixels_filtrados)
        labels_filtrados_gmm = gmm.predict(pixels_filtrados)
        clustered_image_gmm = create_clustered_image(labels_filtrados_gmm)
        results['gmm'] = {
            'image': clustered_image_gmm,
            'labels': labels_filtrados_gmm,
            'model': gmm
        }
    
    # Aplicar K-Nearest Neighbors si se solicita
    if cluster_type.lower() == 'knn' or cluster_type.lower() == 'all':
        # Para KNN necesitamos etiquetas de entrenamiento, usamos K-means si no están disponibles
        if 'kmeans' not in results:
            kmeans = KMeans(n_clusters=n_clusters, random_state=0).fit(pixels_filtrados)
            train_labels = kmeans.labels_
        else:
            train_labels = results['kmeans']['labels']
            
        knn = KNeighborsClassifier(n_neighbors=n_clusters)
        knn.fit(pixels_filtrados, train_labels)
        labels_filtrados_knn = knn.predict(pixels_filtrados)
        clustered_image_knn = create_clustered_image(labels_filtrados_knn)
        results['knn'] = {
            'image': clustered_image_knn,
            'labels': labels_filtrados_knn,
            'model': knn
        }
    
    if visualize and results:
        method_keys = [
            k for k in results
            if isinstance(results[k], dict) and results[k].get("image") is not None
        ]
        n_plots = len(method_keys)
        if n_plots:
            fig, axs = plt.subplots(1, n_plots, figsize=(5 * n_plots, 7))
            if n_plots == 1:
                method = method_keys[0]
                axs.imshow(results[method]["image"], cmap="jet")
                axs.axis("off")
                axs.set_title(method.upper())
            else:
                for i, method in enumerate(method_keys):
                    axs[i].imshow(results[method]["image"], cmap="jet")
                    axs[i].axis("off")
                    axs[i].set_title(method.upper())
            results["_figure"] = fig

    return results

def main(imagery_fp: str, cluster_type: str = 'kmeans', n_clusters: int = 5, 
         visualize: bool = True, output_folder: str = None):
    """
    Función principal para clustering de imágenes.
    
    Args:
        imagery_fp: Ruta al archivo de imagen TIF o carpeta con polígonos
        cluster_type: Tipo de clustering ('kmeans', 'gmm', 'knn', o 'all')
        n_clusters: Número de clusters
        visualize: Si visualizar resultados
    """
    imagery_path = Path(imagery_fp) if imagery_fp else None
    
    if not imagery_path or not imagery_path.exists():
        raise FileNotFoundError(f"La ruta de imagen no existe: {imagery_fp}")
    
    # Si es una carpeta, buscar stacks NDVI en subcarpetas
    if imagery_path.is_dir():
        print(f"📁 Buscando stacks NDVI en: {imagery_path}")
        # Buscar en diferentes patrones posibles
        stack_files = list(imagery_path.rglob("**/STACK/stack_ndvi.tif"))
        
        # Si no se encuentran, buscar también en la estructura alternativa
        if not stack_files:
            # Buscar cualquier stack_ndvi.tif en subdirectorios
            stack_files = list(imagery_path.rglob("stack_ndvi.tif"))
        
        if not stack_files:
            # Listar subdirectorios y verificar si STACK existe pero está vacío
            subdirs = [d for d in imagery_path.iterdir() if d.is_dir()]
            error_msg = f"❌ No se encontraron archivos stack_ndvi.tif en {imagery_path}\n\n"
            error_msg += f"💡 **Solución:** Ejecuta primero el módulo '3_stack' para generar los stacks.\n\n"
            
            if subdirs:
                error_msg += f"📁 Subdirectorios encontrados: {', '.join([d.name for d in subdirs[:5]])}\n"
                # Verificar si existe el directorio STACK pero está vacío
                for subdir in subdirs[:3]:
                    stack_dir = subdir / "STACK"
                    if stack_dir.exists():
                        stack_files_in_dir = list(stack_dir.glob("*.tif"))
                        if not stack_files_in_dir:
                            error_msg += f"\n⚠️  El directorio {stack_dir} existe pero está vacío.\n"
                            error_msg += f"   Ejecuta '3_stack' para generar stack_ndvi.tif\n"
                        else:
                            error_msg += f"\n📄 Archivos encontrados en {stack_dir}: {', '.join([f.name for f in stack_files_in_dir[:3]])}\n"
                    else:
                        error_msg += f"\n📂 Directorio STACK no existe en {subdir.name}/\n"
                        error_msg += f"   Ejecuta '3_stack' para crearlo y generar los stacks\n"
            
            error_msg += f"\n🔗 Orden de ejecución recomendado:\n"
            error_msg += f"   1. 2_all_clipp - Recortar imágenes por polígonos\n"
            error_msg += f"   2. 3_stack - Crear stacks NDVI/EVI (genera stack_ndvi.tif)\n"
            error_msg += f"   3. 4_5_cluster - Visualizar clusters (requiere stacks)\n"
            
            raise ValueError(error_msg)
        
        print(f"📊 Encontrados {len(stack_files)} archivo(s) stack_ndvi.tif")
        
        for stack_file in stack_files:
            try:
                print(f"🔄 Procesando: {stack_file}")
                results = cluster_image(str(stack_file), cluster_type=cluster_type, n_clusters=n_clusters, visualize=visualize)
                
                # Guardar gráfico si hay output_folder
                if output_folder and results:
                    import matplotlib
                    matplotlib.use('Agg')
                    fig = results.get("_figure")
                    if fig is None:
                        method_keys = [
                            k for k in results
                            if isinstance(results[k], dict)
                            and results[k].get("image") is not None
                        ]
                        n_plots = len(method_keys)
                        if n_plots:
                            fig, axs = plt.subplots(1, n_plots, figsize=(5 * n_plots, 7))
                            if n_plots == 1:
                                m0 = method_keys[0]
                                axs.imshow(results[m0]["image"], cmap="jet")
                                axs.axis("off")
                                axs.set_title(m0.upper())
                            else:
                                for i, m in enumerate(method_keys):
                                    axs[i].imshow(results[m]["image"], cmap="jet")
                                    axs[i].axis("off")
                                    axs[i].set_title(m.upper())
                    
                    if fig:
                        output_path = Path(output_folder)
                        output_path.mkdir(parents=True, exist_ok=True)
                        output_file = output_path / f"cluster_{stack_file.parent.parent.name}.png"
                        fig.savefig(output_file, dpi=150, bbox_inches='tight')
                        plt.close(fig)
                        print(f"✅ Gráfico guardado: {output_file}")
                
                print(f"✅ Procesado exitosamente: {stack_file.name}")
            except Exception as e:
                print(f"❌ Error procesando {stack_file}: {str(e)}")
                continue
    else:
        # Es un archivo individual
        print(f"🔄 Procesando archivo: {imagery_path}")
        results = cluster_image(str(imagery_path), cluster_type=cluster_type, n_clusters=n_clusters, visualize=visualize)
        
        # Guardar gráfico si hay output_folder
        if output_folder and results:
            import matplotlib
            matplotlib.use('Agg')
            fig = results.get("_figure")
            if fig is None:
                method_keys = [
                    k for k in results
                    if isinstance(results[k], dict)
                    and results[k].get("image") is not None
                ]
                n_plots = len(method_keys)
                if n_plots:
                    fig, axs = plt.subplots(1, n_plots, figsize=(5 * n_plots, 7))
                    if n_plots == 1:
                        m0 = method_keys[0]
                        axs.imshow(results[m0]["image"], cmap="jet")
                        axs.axis("off")
                        axs.set_title(m0.upper())
                    else:
                        for i, m in enumerate(method_keys):
                            axs[i].imshow(results[m]["image"], cmap="jet")
                            axs[i].axis("off")
                            axs[i].set_title(m.upper())
            
            if fig:
                output_path = Path(output_folder)
                output_path.mkdir(parents=True, exist_ok=True)
                output_file = output_path / f"cluster_{imagery_path.stem}.png"
                fig.savefig(output_file, dpi=150, bbox_inches='tight')
                plt.close(fig)
                print(f"✅ Gráfico guardado: {output_file}")
        
        print(f"✅ Procesado exitosamente")
    
    return results

if __name__ == "__main__":
    # Ejemplo de uso (solo para pruebas)
    imagery_path = '/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/5.RECORTES/464_moniquira/1687.0/STACK/stack_ndvi.tif'
    if Path(imagery_path).exists():
        main(imagery_path, cluster_type='all', n_clusters=5)
    else:
        print("⚠️ Archivo no encontrado. Ejecuta desde la aplicación Streamlit con parámetros correctos.")