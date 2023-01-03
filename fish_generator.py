from bpy import context, ops, data
from mathutils import Vector
import random
import numpy as np
import bmesh
import copy
import math

# dane potrzebne do miejsca generowania innych elementów
corpus_length = 10.
corpus_height = 5.
corpus_width = 5.

# dane do funkcji dopasowania
fit_shells = 0
all_shells = 0
roundness_ratio = 0


# reguła 30, reguła 54 - do generowania łusek
def rule54_find(x: int, y: int, z: int) -> int:
    if x == y == z == 1:
        return 0
    if x == y == 1 and z == 0:
        return 0
    if x == z == 1 and y == 0:
        return 1
    if x == 1 and y == z == 0:
        return 1
    if x == 0 and y == z == 1:
        return 0
    if x == z == 0 and y == 1:
        return 1
    if x == y == 0 and z == 1:
        return 1
    return 0


# określenie czy kolor jest ciemny na podstawie HSP http://alienryderflex.com/hsp.html
def hsp_is_dark(color) -> bool:
    r = color[0] * 255
    g = color[1] * 255
    b = color[2] * 255
    hsp = math.sqrt(0.299 * (r * r) + 0.587 * (g * g) + 0.114 * (b * b))
    return hsp <= 127.5


def rule54_gen():
    global fit_shells, all_shells
    
    ops.object.mode_set(mode='EDIT')
    dims = 144
    all_shells += dims * dims
    values = np.zeros([dims, dims])
    for x in range(dims):
        values[x][0] = random.randint(0, 1)

    for y in range(1, dims):
        for x in range(1, dims - 1):
            values[x][y] = rule54_find(values[x - 1][y - 1], values[x][y - 1], values[x + 1][y - 1])
        values[0][y] = rule54_find(0, values[0][y - 1], values[1][y - 1])
        values[dims - 1][y] = rule54_find(values[dims - 2][y - 1], values[dims - 1][y - 1], 0)
    
    # trzeba transponować, żeby obrócić zdj o 90 stopni
    values = np.transpose(values)
    pixels = [None] * dims * dims
    
    color1 = [random.random(), random.random(), random.random(), 1]
    color2 = [1-color1[0], 1-color1[1], 1-color1[2], 1]
    color1_dark = hsp_is_dark(color1)
    color2_dark = hsp_is_dark(color2)
    
    for y in range(dims):
        for x in range(dims):
            if values[x][y] == 1:
                pixels[(x * dims) + y] = color1
                if color1_dark == True:
                    fit_shells += 1
            else:
                pixels[(x * dims) + y] = color2
                if color2_dark == True:
                    fit_shells += 1
                
    # spłaszczam listę
    pixels = [item for sublist in pixels for item in sublist]
    
    image = data.images.new("ShellsImage", width=dims, height=dims)
    image.pixels = pixels
    #image.filepath_raw = "D:/Studia/PWK/temp.png"
    #image.file_format = 'PNG'
    #image.save()
        
    return image


def solidify(mesh_name: str, width: float):
    ops.object.mode_set(mode='OBJECT')

    # konwersja w siatke
    ops.object.convert(target='MESH', keep_original=True)
    mesh = context.active_object
    mesh.name = mesh_name

    ops.object.mode_set(mode='EDIT')

    # wybranie wszystkich wierzcholkow
    ops.mesh.select_all(action='SELECT')

    # wypelnienie
    ops.mesh.edge_face_add()

    # dodanie trojkatow
    ops.mesh.quads_convert_to_tris(ngon_method='BEAUTY')

    ops.mesh.select_all(action='SELECT')

    # konwersja trojkatow do czworokatow
    ops.mesh.tris_convert_to_quads(
        face_threshold=1.396264, shape_threshold=1.396264)

    # wstawienie scian
    # iter_range = range(0, 1, 1)
    # for i in iter_range:
    ops.mesh.inset(thickness=0.25, use_relative_offset=True)

    ops.object.mode_set(mode='OBJECT')

    solidify = mesh.modifiers.new(type='SOLIDIFY', name='Solidify')
    solidify.offset = 0.0
    solidify.thickness = width

    subsurf = mesh.modifiers.new(type='SUBSURF', name='Subsurf')
    subsurf.levels = subsurf.render_levels = 3
    
    #kolorowanie
    ob = context.active_object
    mat = data.materials.new(name="Colour")
    mat.diffuse_color = [random.random(), random.random(), random.random(), 1]
    ob.data.materials.append(mat)
    

# losowanie typów krawędzi bezier pointsów
def draw_point_type() -> str:
    return random.choice(['FREE', 'VECTOR', 'ALIGNED', 'AUTO'])


def draw_point_type_weighted() -> str:
    return random.choices(['FREE', 'VECTOR', 'ALIGNED', 'AUTO'], weights=(0.2, 0.2, 0.2, 0.4), k=1)[0]


def generate_corpus(length: float, height: float, width: float):
    # utworzenie krzywej
    ops.curve.primitive_bezier_circle_add(enter_editmode=True)
    # ops.curve. subdivide()
    curve = context.active_object
    curve.name = 'Corpus Curve'
    bez_points = curve.data.splines[0].bezier_points

    round_type = 0
    for bez_point in bez_points:
        bez_point.handle_left_type = draw_point_type_weighted()
        bez_point.handle_right_type = draw_point_type_weighted()
        if bez_point.handle_left_type == 'AUTO':
            round_type += 1
        if bez_point.handle_right_type == 'AUTO':
            round_type += 1
            
    # obliczam stosunek okrągłości
    global roundness_ratio
    roundness_ratio = round_type / 8

    proportions = random.uniform(1.3, 8.9)

    # lewy
    bez_points[0].co = Vector((-length, 0.0, 0.0))
    bez_points[0].handle_left = Vector((-length, -1.0, 0.0))
    bez_points[0].handle_right = Vector((-length, 1.0, 0.0))

    # gora
    bez_points[1].co = Vector((-length / proportions, height / 2, 0.0))
    bez_points[1].handle_left = Vector((-length / proportions - 1, height / 2, 0.0))
    bez_points[1].handle_right = Vector((-length / proportions + 1, height / 2, 0.0))

    # poczatek ogona
    bez_points[2].co = Vector((0.0, 0.0, 0.0))
    bez_points[2].handle_left = Vector((0.0, 1.0, 0.0))
    bez_points[2].handle_right = Vector((0.0, -1.0, 0.0))

    # dolny
    bez_points[3].co = Vector((-length / proportions, -height / 2, 0.0))
    bez_points[3].handle_left = Vector((-length / proportions + 1, -height / 2, 0.0))
    bez_points[3].handle_right = Vector((-length / proportions - 1, -height / 2, 0.0))

    solidify('Corpus Mesh', width)
    obj = context.active_object

    # dostęp do nadpisania zmiennych globalnych
    global corpus_length, corpus_height, corpus_width
    corpus_length = length
    corpus_height = height / 2
    corpus_width = width / 2


def generate_tail(length: float, height: float, width: float, indentation: float):
    global corpus_width
    if corpus_width < width:
        width = corpus_width
        
    # utworzenie krzywej
    ops.curve.primitive_bezier_circle_add(enter_editmode=True)
    curve = context.active_object
    curve.name = 'Tail Curve'
    bez_points = curve.data.splines[0].bezier_points

    for bez_point in bez_points:
        bez_point.handle_left_type = draw_point_type()
        bez_point.handle_right_type = draw_point_type()

    # lewy
    bez_points[0].co = Vector((-1, 0.0, 0.0))
    bez_points[0].handle_left = Vector((-1, -1.0, 0.0))
    bez_points[0].handle_right = Vector((-1, 1.0, 0.0))

    # gora
    twist = random.uniform(-length / 3, length / 3)
    bez_points[1].co = Vector((length, height / 2, twist))
    bez_points[1].handle_left = Vector((length, height / 2 + 1, twist))
    bez_points[1].handle_right = Vector((length, height / 2 - 1, twist))

    # srodek
    twist = random.uniform(-length / 3, length / 3)
    bez_points[2].co = Vector((length - indentation, 0.0, twist))
    bez_points[2].handle_left = Vector((length - indentation, 0.1, twist))
    bez_points[2].handle_right = Vector((length - indentation, -0.1, twist))

    # dolny
    twist = random.uniform(-length / 3, length / 3)
    bez_points[3].co = Vector((length, -height / 2, twist))
    bez_points[3].handle_left = Vector((length, -height / 2 + 1, twist))
    bez_points[3].handle_right = Vector((length, -height / 2 - 1, twist))

    solidify('Tail Mesh', width)


def generate_upper_fin(length: float, height: float, width: float):
    global corpus_width, corpus_height
    if corpus_width < width:
        width = corpus_width - 2
    if corpus_height > height:
        height = corpus_height + 2
    

    # utworzenie krzywej
    ops.curve.primitive_bezier_circle_add(enter_editmode=True)
    curve = context.active_object
    curve.name = 'Upper Fin Curve'
    bez_points = curve.data.splines[0].bezier_points

    for bez_point in bez_points:
        bez_point.handle_left_type = draw_point_type()
        bez_point.handle_right_type = draw_point_type()

    most_left_point_x = random.uniform(-2 * corpus_length / 3, -corpus_length / 4)

    # lewy dolny
    bez_points[0].co = Vector((most_left_point_x, corpus_height / 2, 0.0))
    bez_points[0].handle_left = Vector((most_left_point_x - 1, corpus_height / 2, 0.0))
    bez_points[0].handle_right = Vector((most_left_point_x + 1, corpus_height / 2, 0.0))

    # prawy dolny
    bez_points[1].co = Vector((most_left_point_x + length, corpus_height / 2, 0.0))
    bez_points[1].handle_left = Vector((most_left_point_x + length, corpus_height / 2 - 1, 0.0))
    bez_points[1].handle_right = Vector((most_left_point_x + length, corpus_height / 2 + 1, 0.0))

    # prawy górny
    twist = random.uniform(-length / 3, length / 3)
    bez_points[2].co = Vector((most_left_point_x + length, corpus_height / 2 + height, twist))
    bez_points[2].handle_left = Vector((most_left_point_x + length, corpus_height / 2 + height, twist))
    bez_points[2].handle_right = Vector((most_left_point_x + length, corpus_height / 2 + height, twist))

    # lewy górny
    twist = random.uniform(-length / 3, length / 3)
    bez_points[3].co = Vector((most_left_point_x, corpus_height / 2 + height / 2, twist))
    bez_points[3].handle_left = Vector((most_left_point_x, corpus_height / 2 + height / 2, twist))
    bez_points[3].handle_right = Vector((most_left_point_x, corpus_height / 2 + height / 2, twist))

    solidify('Upper Fin Mesh', width)
    
    
def generate_eyes():
    # utworzenie krzywej
    ops.curve.primitive_bezier_circle_add(enter_editmode=True)
    curve = context.active_object
    curve.name = 'Eyes Curve'
    bez_points = curve.data.splines[0].bezier_points

    for bez_point in bez_points:
        bez_point.handle_left_type = draw_point_type()
        bez_point.handle_right_type = draw_point_type()

    x_center = -2*corpus_length/3
    y_center = corpus_height / 3
    # lewy
    bez_points[0].co = Vector((x_center - 1, y_center, 0.0))
    bez_points[0].handle_left = Vector((x_center - 1, y_center - 1, 0.0))
    bez_points[0].handle_right = Vector((x_center - 1, y_center + 1, 0.0))

    # góra
    bez_points[1].co = Vector((x_center, y_center + 1, 0.0))
    bez_points[1].handle_left = Vector((x_center - 1, y_center + 1, 0.0))
    bez_points[1].handle_right = Vector((x_center + 1, y_center + 1, 0.0))

    # prawo
    bez_points[2].co = Vector((x_center + 1, y_center, 0.0))
    bez_points[2].handle_left = Vector((x_center + 1, y_center + 1, 0.0))
    bez_points[2].handle_right = Vector((x_center + 1, y_center - 1, 0.0))

    # dół
    bez_points[3].co = Vector((x_center, y_center - 1, 0.0))
    bez_points[3].handle_left = Vector((x_center + 1, y_center - 1, 0.0))
    bez_points[3].handle_right = Vector((x_center - 1, y_center - 1, 0.0))

    global corpus_width
    solidify('Eyes Mesh', corpus_width + 4)


def generate_side_fins(length: float, height: float, width: float):
    global corpus_width
    if corpus_width > height:
        height = corpus_width + 2
        
    # utworzenie krzywej
    ops.curve.primitive_bezier_circle_add(enter_editmode=True)
    curve = context.active_object
    curve.name = 'Left Fin Curve'
    bez_points = curve.data.splines[0].bezier_points

    for bez_point in bez_points:
        bez_point.handle_left_type = 'AUTO'
        bez_point.handle_right_type = 'AUTO'

    x = random.uniform(-2 * corpus_length / 3, -corpus_length / 4)
    x2 = x
    y = random.uniform(-corpus_height / 3, 0)
    # środek
    bez_points[0].co = Vector((x, y, 0.0))
    bez_points[0].handle_left = Vector((x - 1, y, 0.0))
    bez_points[0].handle_right = Vector((x + 1, y, 0.0))

    y = random.uniform(-corpus_height / 3, 0)
    # prawy
    bez_points[1].co = Vector((x + length, y, height))
    bez_points[1].handle_left = Vector((x + length + 1, y, height))
    bez_points[1].handle_right = Vector((x + length - 1, y, height))

    # środkowy 2
    cut = random.uniform(height / 2, height)
    x = random.uniform(-corpus_length / 3, x)
    bez_points[2].co = Vector((x, y, cut))
    bez_points[2].handle_left = Vector((x - 1, y, cut))
    bez_points[2].handle_right = Vector((x + 1, y, cut))

    # lewy
    bez_points[3].co = Vector((x2, y, height))
    bez_points[3].handle_left = Vector((x2 - 1, y, height))
    bez_points[3].handle_right = Vector((x2 + 1, y, height))

    # trzeba zrobić kopię, gdyż dane się gubiły po solidify
    vectors = []
    for bez_point in bez_points:
        vectors.append(copy.copy(bez_point.co))
        vectors.append(copy.copy(bez_point.handle_left))
        vectors.append(copy.copy(bez_point.handle_right))
    
    solidify('Left Fin Mesh', width)
    
    # utworzenie krzywej
    ops.curve.primitive_bezier_circle_add(enter_editmode=True)
    curve = context.active_object
    curve.name = 'Right Fin Curve'
    mirrored_bez_points = curve.data.splines[0].bezier_points
    
    for p in range(len(mirrored_bez_points)):
        mirrored_bez_points[p].handle_left_type = 'AUTO'
        mirrored_bez_points[p].handle_right_type = 'AUTO'
        point = vectors[p * 3]
        mirrored_bez_points[p].co = Vector((point.x, point.y, -point.z))
        point = vectors[p * 3 + 1]
        mirrored_bez_points[p].handle_left = Vector((point.x, point.y, -point.z))
        point = vectors[p * 3 + 2]
        mirrored_bez_points[p].handle_right = Vector((point.x, point.y, -point.z))

    solidify('Right Fin Mesh', width)
    
    
def generate_shells(mesh_name: str):
    ops.object.mode_set(mode='OBJECT')
    ops.object.select_all(action='DESELECT')

    context.view_layer.objects.active = data.objects[mesh_name]
    ob = context.object
    me = ob.data
    # nowy mesh
    bm = bmesh.new()
    # wczytanie mesha
    bm.from_mesh(me)
    # podział na więcej ścian
    #bmesh.ops.subdivide_edges(bm,edges=bm.edges,cuts=1,use_grid_fill=True)
    # zapisanie spowrotem
    bm.to_mesh(me)
    me.update()

    ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(me)
    bm.faces.ensure_lookup_table()
    # ustawienie face select mode
    #context.tool_settings.mesh_select_mode = [False, False, True]

    i=0
    for face in bm.faces:
        face.select = True
        mat = data.materials.new(name="Colour")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        texImage = mat.node_tree.nodes.new('ShaderNodeTexImage')
        texImage.image = rule54_gen()
        mat.node_tree.links.new(bsdf.inputs['Base Color'], texImage.outputs['Color'])
        # uwydatnienie kolorów
        mat.node_tree.nodes['Image Texture'].projection = 'BOX'
        mat.node_tree.nodes['Image Texture'].interpolation = 'Closest'
        ob.data.materials.append(mat)
        context.object.active_material_index=i
        ops.object.material_slot_assign()
        ops.uv.cube_project()
        i += 1
        face.select = False

    bmesh.update_edit_mesh(me)
    

def delete_all_from_scene():
    # Select objects by type
    ops.object.mode_set(mode='OBJECT')
    for o in context.scene.objects:
        if o.type == 'MESH':
            o.select_set(True)
        else:
            o.select_set(False)
    # Call the operator only once
    ops.object.delete()
    
    for bpy_data_iter in (data.objects, data.meshes):
        for id_data in bpy_data_iter:
            bpy_data_iter.remove(id_data)
    # iterate over all images in the file
    for image in data.images:
        # don't do anything if the image has any users.
        if image.users:
            continue
        # remove the image otherwise
        data.images.remove(image)
     
     
def random_bigger_num() -> int:
    return random.randint(8, 33)


def random_smaller_num() -> int:
    return random.randint(1, 7)


def random_smallest_num() -> float:
    return random.uniform(0, 1)


def random_num() -> int:
    return random.randint(3, 33)
            
            
def fitting_function(roundness_threshold: float, color_threshold: float) -> bool:
    print("Stosunek okrągłości: " + str(roundness_ratio))
    print("Próg dopasowania okrągłości: " + str(roundness_threshold))
    
    dark_ratio = fit_shells / all_shells
    print("\nStosunek ciemnego koloru korpusu do jasnego: " + str(dark_ratio))
    print("Próg dopasowania ciemności kolorów: " + str(color_threshold))
    
    res = False
    if roundness_threshold <= roundness_ratio and color_threshold <= dark_ratio:
        res = True
    
    print("\nWynik funkcji dopasowania: " + str(res))
    return res


delete_all_from_scene()

generate_corpus(random_bigger_num(), random_bigger_num(), random_smaller_num())
generate_eyes()
generate_tail(random_num(), random_num(), random_smaller_num(), random_smallest_num())
generate_upper_fin(random_smaller_num(), random_num(), random_smaller_num())
generate_side_fins(random_smaller_num(), random_smaller_num(), random_smallest_num())

generate_shells("Corpus Mesh")

fitting_function(0.3, 0.4)
