import numpy as np

import importlib

from wrl_library import open_raster, open_radolan_dataset, create_osr, get_radolan_grid, reproject

osr = import_optional("osgeo.osr")

proj_stereo = create_osr("dwd-radolan")
proj_wgs = osr.SpatialReference()
proj_wgs.ImportFromEPSG(4326)
radolan_grid_xy = get_radolan_grid(1200, 1100)
radolan_grid_ll = reproject(radolan_grid_xy, projection_source=proj_stereo, projection_target=proj_wgs)
new_coords = dict(lon=(["y", "x"], radolan_grid_ll[:, :, 0]), lat=(["y", "x"], radolan_grid_ll[:, :, 1]))
print(type(new_coords))
print(new_coords)

lon = new_coords['lon']
print(lon)
print(len(lon))
print(type(lon[1]))

with open("lon_array.npy", "wb") as f:
    np.save(f, new_coords['lon'][1])

with open("lat_array.npy", "wb") as f:
    np.save(f, new_coords['lat'][1])


with open("lon_array.npy", "rb") as f:
    lon_array = np.load(f)
        
with open("lat_array.npy", "rb") as f:
    lat_array = np.load(f)

new_coords_new = {
    'lon': (['y', 'x'], lon_array), 'lat': (['y', 'x'], lat_array)
}

print(new_coords)
print(new_coords_new)


tile_file = "ESRI_Satellite_DE_rgb_rescaled.tif"
ds = open_raster(tile_file)
r = ds.GetRasterBand(1).ReadAsArray()
g = ds.GetRasterBand(2).ReadAsArray()
b = ds.GetRasterBand(3).ReadAsArray()
rgb = np.dstack((r, g, b))
rgb = np.rot90(rgb, k=3)

with open("satellite.npy", "wb") as f:
    np.save(f, rgb)
