"""
Utilities used by example notebooks
"""

import rasterio
import numpy as np
from utils import plot_image
import matplotlib.pyplot as plt

tif_path = "/home/cristianrr/satellital/downloads/04-2024.tif"

with rasterio.open(tif_path) as src:
    print("Número de bandas:", src.count)
    cube = src.read()   


cube_hwc = np.transpose(cube, (1, 2, 0))
print("Cubo HWC:", cube_hwc.shape)

rgb = cube_hwc[..., [3, 2, 1]].astype(np.float32)

print("RGB global – dtype:", rgb.dtype,
      "min:", rgb.min(),
      "max:", rgb.max())

# imprime por canal
for i, color in enumerate(("R","G","B")):
    channel = rgb[..., i]
    print(f"  {color} channel – min:", channel.min(),
          " max:", channel.max())

rgb /= 10000.0

plot_image(rgb, clip_range=(0,1))
plt.show()