import math

def create_chitanda_obj():
    vertices = []
    faces = {}
    current_mat = None

    def set_mat(mat):
        nonlocal current_mat
        current_mat = mat
        if mat not in faces:
            faces[mat] = []

    def add_v(x, y, z):
        vertices.append((x, y, z))
        return len(vertices)

    def add_box(cx, cy, cz, sx, sy, sz, mat):
        set_mat(mat)
        hx, hy, hz = sx/2, sy/2, sz/2
        v = [
            add_v(cx - hx, cy - hy, cz - hz),
            add_v(cx + hx, cy - hy, cz - hz),
            add_v(cx + hx, cy + hy, cz - hz),
            add_v(cx - hx, cy + hy, cz - hz),
            add_v(cx - hx, cy - hy, cz + hz),
            add_v(cx + hx, cy - hy, cz + hz),
            add_v(cx + hx, cy + hy, cz + hz),
            add_v(cx - hx, cy + hy, cz + hz)
        ]
        quads = [
            (v[0], v[1], v[2], v[3]),
            (v[5], v[4], v[7], v[6]),
            (v[4], v[0], v[3], v[7]),
            (v[1], v[5], v[6], v[2]),
            (v[3], v[2], v[6], v[7]),
            (v[4], v[5], v[1], v[0])
        ]
        for q in quads:
            faces[current_mat].append((q[0], q[1], q[2]))
            faces[current_mat].append((q[0], q[2], q[3]))

    def add_cylinder(cx, cy, cz, r_top, r_bot, height, segments, mat):
        set_mat(mat)
        h2 = height / 2
        top_ring = []
        bot_ring = []
        for i in range(segments):
            angle = (2 * math.pi * i) / segments
            x = math.cos(angle)
            z = math.sin(angle)
            top_ring.append(add_v(cx + x * r_top, cy + h2, cz + z * r_top))
            bot_ring.append(add_v(cx + x * r_bot, cy - h2, cz + z * r_bot))
        
        top_center = add_v(cx, cy + h2, cz)
        bot_center = add_v(cx, cy - h2, cz)

        for i in range(segments):
            i_next = (i + 1) % segments
            faces[current_mat].append((bot_ring[i], bot_ring[i_next], top_ring[i_next]))
            faces[current_mat].append((bot_ring[i], top_ring[i_next], top_ring[i]))
            faces[current_mat].append((top_center, top_ring[i], top_ring[i_next]))
            faces[current_mat].append((bot_center, bot_ring[i_next], bot_ring[i]))

    def add_sphere(cx, cy, cz, radius, lat_seg, lon_seg, mat, scale_y=1.0):
        set_mat(mat)
        grid = []
        for i in range(lat_seg + 1):
            lat = math.pi * i / lat_seg - math.pi / 2
            row = []
            for j in range(lon_seg):
                lon = 2 * math.pi * j / lon_seg
                x = math.cos(lat) * math.cos(lon) * radius
                y = math.sin(lat) * radius * scale_y
                z = math.cos(lat) * math.sin(lon) * radius
                row.append(add_v(cx + x, cy + y, cz + z))
            grid.append(row)

        for i in range(lat_seg):
            for j in range(lon_seg):
                j_next = (j + 1) % lon_seg
                v1 = grid[i][j]
                v2 = grid[i][j_next]
                v3 = grid[i+1][j_next]
                v4 = grid[i+1][j]
                faces[current_mat].append((v1, v2, v3))
                faces[current_mat].append((v1, v3, v4))

    # --- BUILD CHITANDA ERU 3D MODEL GEOMETRY ---
    # Chitanda Eru from Hyouka (Kamiyama High School Sailor Uniform)

    # 1. Head & Face
    add_sphere(0, 1.62, 0, 0.22, 12, 16, "SkinMat", scale_y=1.05)
    
    # Chitanda's iconic large sparkling Violet Eyes ("Watashi, kininarimasu!")
    add_box(-0.075, 1.63, 0.20, 0.05, 0.065, 0.02, "VioletEyes")
    add_box(0.075, 1.63, 0.20, 0.05, 0.065, 0.02, "VioletEyes")
    # Eye highlights (sparkles)
    add_box(-0.065, 1.65, 0.21, 0.015, 0.015, 0.01, "WhiteClean")
    add_box(0.085, 1.65, 0.21, 0.015, 0.015, 0.01, "WhiteClean")

    # 2. Chitanda's Long Glossy Black/Purple Hair
    # Main scalp volume
    add_sphere(0, 1.68, -0.04, 0.245, 12, 16, "DarkHair", scale_y=1.02)
    # Front Bangs
    add_box(0, 1.76, 0.17, 0.26, 0.14, 0.06, "DarkHair")
    # Side Bang strands (framing cheeks)
    add_box(-0.19, 1.54, 0.10, 0.05, 0.35, 0.08, "DarkHair")
    add_box(0.19, 1.54, 0.10, 0.05, 0.35, 0.08, "DarkHair")
    # Long Back Hair flowing down to waist
    add_box(0, 1.30, -0.16, 0.34, 0.70, 0.08, "DarkHair")
    add_box(0, 0.90, -0.15, 0.30, 0.40, 0.06, "DarkHair")

    # 3. Kamiyama High School Uniform
    # White Sailor Blouse (Torso)
    add_cylinder(0, 1.25, 0, 0.20, 0.18, 0.44, 12, "WhiteUniform")
    # Navy Sailor Collar flap across shoulders
    add_box(0, 1.42, -0.08, 0.34, 0.06, 0.22, "NavyTrim")
    # Sailor Cyan/Blue Ribbon Tie at chest
    add_box(0, 1.34, 0.18, 0.08, 0.12, 0.04, "RibbonCyan")
    add_box(0, 1.26, 0.17, 0.05, 0.10, 0.03, "RibbonCyan")

    # 4. Arms (White short/medium sleeves)
    # Left Arm
    add_cylinder(-0.26, 1.30, 0, 0.09, 0.08, 0.24, 10, "WhiteUniform") # Sleeve
    add_cylinder(-0.26, 1.10, 0, 0.06, 0.055, 0.26, 10, "SkinMat") # Forearm
    add_sphere(-0.26, 0.94, 0, 0.055, 6, 8, "SkinMat") # Hand

    # Right Arm
    add_cylinder(0.26, 1.30, 0, 0.09, 0.08, 0.24, 10, "WhiteUniform") # Sleeve
    add_cylinder(0.26, 1.10, 0, 0.06, 0.055, 0.26, 10, "SkinMat") # Forearm
    add_sphere(0.26, 0.94, 0, 0.055, 6, 8, "SkinMat") # Hand

    # 5. Pleated Navy Blue High-School Skirt
    add_cylinder(0, 0.92, 0, 0.19, 0.32, 0.34, 16, "NavyTrim")

    # 6. Legs (Skin & Knee-high Black Socks)
    # Left Leg
    add_cylinder(-0.11, 0.70, 0, 0.08, 0.075, 0.22, 10, "SkinMat") # Upper thigh
    add_cylinder(-0.11, 0.44, 0, 0.075, 0.065, 0.38, 10, "BlackSocks") # Knee-high sock
    add_box(-0.11, 0.22, 0.04, 0.09, 0.06, 0.18, "BrownLoafer") # Brown School Loafer

    # Right Leg
    add_cylinder(0.11, 0.70, 0, 0.08, 0.075, 0.22, 10, "SkinMat") # Upper thigh
    add_cylinder(0.11, 0.44, 0, 0.075, 0.065, 0.38, 10, "BlackSocks") # Knee-high sock
    add_box(0.11, 0.22, 0.04, 0.09, 0.06, 0.18, "BrownLoafer") # Brown School Loafer

    # Write OBJ File
    with open("chitanda_eru.obj", "w") as f:
        f.write("# Chitanda Eru 3D Model (Hyouka)\n")
        f.write("mtllib chitanda_eru.mtl\n\n")
        for v in vertices:
            f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
        for mat, face_list in faces.items():
            f.write(f"\nusemtl {mat}\n")
            for face in face_list:
                f.write(f"f {face[0]} {face[1]} {face[2]}\n")

    # Write MTL File
    with open("chitanda_eru.mtl", "w") as f:
        f.write("# Chitanda Eru Materials\n\n")
        materials = {
            "SkinMat": "1.0 0.88 0.82",
            "VioletEyes": "0.48 0.18 0.75", # Chitanda's signature violet eyes
            "WhiteClean": "1.0 1.0 1.0",
            "DarkHair": "0.12 0.12 0.18", # Dark glossy purple/black hair
            "WhiteUniform": "0.96 0.96 0.98",
            "NavyTrim": "0.10 0.14 0.26", # Kamiyama sailor navy
            "RibbonCyan": "0.15 0.55 0.80", # Blue neckerchief ribbon
            "BlackSocks": "0.08 0.08 0.10",
            "BrownLoafer": "0.28 0.16 0.10"
        }
        for mat_name, diffuse in materials.items():
            f.write(f"newmtl {mat_name}\n")
            f.write(f"Kd {diffuse}\n")
            f.write(f"Ka 0.2 0.2 0.2\n")
            f.write(f"Ks 0.2 0.2 0.2\n")
            f.write(f"d 1.0\n")
            f.write(f"illum 2\n\n")

    print(f"Generated chitanda_eru.obj with {len(vertices)} vertices and {sum(len(f) for f in faces.values())} polygons!")

if __name__ == "__main__":
    create_chitanda_obj()
