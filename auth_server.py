from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.serving import run_simple
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'transporte_aguila.db')
import sqlite3
import secrets
import re
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DATABASE = 'transporte_aguila.db'

def init_db():
    """Inicializa la base de datos con las tablas necesarias"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Crear tabla de usuarios con tipo de usuario
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            telefono TEXT NOT NULL,
            cedula TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            tipo_usuario TEXT CHECK(tipo_usuario IN ('pasajero', 'conductor')) DEFAULT 'pasajero',
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ultimo_acceso TIMESTAMP
        )
    ''')
    
    # Crear tabla de conductores con información adicional
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conductores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER UNIQUE NOT NULL,
            numero_licencia TEXT UNIQUE NOT NULL,
            categoria_licencia TEXT NOT NULL,
            fecha_vencimiento_licencia DATE NOT NULL,
            años_experiencia INTEGER,
            vehiculo_propio BOOLEAN DEFAULT FALSE,
            disponible BOOLEAN DEFAULT TRUE,
            calificacion_promedio REAL DEFAULT 0.0,
            viajes_completados INTEGER DEFAULT 0,
            estado TEXT CHECK(estado IN ('pendiente', 'aprobado', 'rechazado', 'suspendido')) DEFAULT 'pendiente',
            fecha_aprobacion TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Crear tabla de vehículos de conductores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehiculos_conductores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conductor_id INTEGER NOT NULL,
            placa TEXT UNIQUE NOT NULL,
            tipo_vehiculo TEXT CHECK(tipo_vehiculo IN ('moto', 'carro', 'bus', '4x4')),
            marca TEXT,
            modelo TEXT,
            year INTEGER,
            capacidad_pasajeros INTEGER,
            color TEXT,
            soat_vigente BOOLEAN DEFAULT FALSE,
            tecnicomecanica_vigente BOOLEAN DEFAULT FALSE,
            activo BOOLEAN DEFAULT TRUE,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conductor_id) REFERENCES conductores (id)
        )
    ''')
    
    # Crear tabla de solicitudes de servicio
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS solicitudes_servicio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_solicitud TEXT UNIQUE NOT NULL,
            usuario_id INTEGER NOT NULL,
            conductor_id INTEGER,
            tipo_vehiculo TEXT NOT NULL,
            origen TEXT NOT NULL,
            destino TEXT NOT NULL,
            fecha_servicio DATE NOT NULL,
            hora_servicio TIME NOT NULL,
            numero_pasajeros INTEGER NOT NULL,
            telefono_contacto TEXT NOT NULL,
            observaciones TEXT,
            precio_estimado INTEGER,
            precio_final INTEGER,
            estado TEXT CHECK(estado IN ('pendiente', 'aceptada', 'en_curso', 'completada', 'cancelada')) DEFAULT 'pendiente',
            fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_aceptacion TIMESTAMP,
            fecha_completacion TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
            FOREIGN KEY (conductor_id) REFERENCES conductores (id)
        )
    ''')
    
    # Crear tabla de calificaciones
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calificaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            solicitud_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            conductor_id INTEGER NOT NULL,
            puntuacion INTEGER CHECK(puntuacion >= 1 AND puntuacion <= 5),
            comentario TEXT,
            fecha_calificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (solicitud_id) REFERENCES solicitudes_servicio (id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
            FOREIGN KEY (conductor_id) REFERENCES conductores (id)
        )
    ''')
    
    # Mantener las tablas existentes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sesiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            token TEXT UNIQUE NOT NULL,
            fecha_expiracion TIMESTAMP,
            activa BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rutas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origen TEXT NOT NULL,
            destino TEXT NOT NULL,
            distancia_km INTEGER,
            duracion_horas REAL,
            precio_base INTEGER,
            tipo_ruta TEXT CHECK(tipo_ruta IN ('urbana', 'intermunicipal', 'rural')),
            activa BOOLEAN DEFAULT TRUE,
            descripcion TEXT,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT UNIQUE NOT NULL,
            tipo_vehiculo TEXT CHECK(tipo_vehiculo IN ('moto', 'carro', 'bus', '4x4')),
            capacidad_pasajeros INTEGER NOT NULL,
            marca TEXT,
            modelo TEXT,
            year INTEGER,
            activo BOOLEAN DEFAULT TRUE,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS horarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ruta_id INTEGER NOT NULL,
            vehiculo_id INTEGER NOT NULL,
            fecha_salida DATETIME NOT NULL,
            fecha_llegada DATETIME,
            precio INTEGER NOT NULL,
            asientos_disponibles INTEGER NOT NULL,
            estado TEXT CHECK(estado IN ('programado', 'en_curso', 'completado', 'cancelado')) DEFAULT 'programado',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ruta_id) REFERENCES rutas (id),
            FOREIGN KEY (vehiculo_id) REFERENCES vehiculos (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_reserva TEXT UNIQUE NOT NULL,
            usuario_id INTEGER NOT NULL,
            horario_id INTEGER NOT NULL,
            numero_asiento INTEGER,
            nombre_pasajero TEXT NOT NULL,
            cedula_pasajero TEXT NOT NULL,
            telefono_pasajero TEXT NOT NULL,
            email_pasajero TEXT NOT NULL,
            precio_total INTEGER NOT NULL,
            estado TEXT CHECK(estado IN ('pendiente', 'confirmada', 'pagada', 'cancelada')) DEFAULT 'pendiente',
            fecha_reserva TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_vencimiento DATETIME,
            notas TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
            FOREIGN KEY (horario_id) REFERENCES horarios (id)
        )
    ''')
    
    # Insertar datos de ejemplo si no existen
    cursor.execute('SELECT COUNT(*) FROM rutas')
    if cursor.fetchone()[0] == 0:
        rutas_ejemplo = [
            ('Quibdó', 'Tadó', 85, 2.5, 18000, 'intermunicipal', 'Ruta principal hacia Tadó'),
            ('Quibdó', 'Istmina', 72, 1.75, 15000, 'intermunicipal', 'Conexión frecuente con Istmina'),
            ('Quibdó', 'Condoto', 95, 2.25, 20000, 'intermunicipal', 'Hacia municipio minero'),
            ('Centro', 'Kennedy', 8, 0.33, 3000, 'urbana', 'Ruta urbana centro-Kennedy'),
            ('Quibdó', 'Bagadó', 125, 3.5, 28000, 'rural', 'Terrenos difíciles')
        ]
        
        cursor.executemany('''
            INSERT INTO rutas (origen, destino, distancia_km, duracion_horas, precio_base, tipo_ruta, descripcion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', rutas_ejemplo)
        
        vehiculos_ejemplo = [
            ('ABC123', 'bus', 35, 'Mercedes', 'Sprinter', 2020),
            ('DEF456', 'bus', 28, 'Chevrolet', 'NPR', 2019),
            ('GHI789', 'carro', 4, 'Toyota', 'Hiace', 2021),
            ('JKL012', '4x4', 7, 'Toyota', 'Land Cruiser', 2018),
            ('MNO345', 'moto', 1, 'Yamaha', 'XTZ', 2022)
        ]
        
        cursor.executemany('''
            INSERT INTO vehiculos (placa, tipo_vehiculo, capacidad_pasajeros, marca, modelo, year)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', vehiculos_ejemplo)
    
    conn.commit()
    conn.close()

def validar_email(email):
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(patron, email) is not None

def validar_password(password):
    if len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres"
    if not re.search(r'[A-Za-z]', password):
        return False, "La contraseña debe contener al menos una letra"
    if not re.search(r'[0-9]', password):
        return False, "La contraseña debe contener al menos un número"
    return True, "Contraseña válida"

def obtener_usuario_por_email(email):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM usuarios WHERE email = ?', (email,))
    usuario = cursor.fetchone()
    conn.close()
    return usuario

def crear_usuario(nombre, apellido, email, telefono, cedula, password, tipo_usuario='pasajero'):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM usuarios WHERE email = ? OR cedula = ?', (email, cedula))
        if cursor.fetchone():
            conn.close()
            return False, "El email o cédula ya están registrados"
        
        password_hash = generate_password_hash(password)
        
        cursor.execute('''
            INSERT INTO usuarios (nombre, apellido, email, telefono, cedula, password_hash, tipo_usuario)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (nombre, apellido, email, telefono, cedula, password_hash, tipo_usuario))
        
        conn.commit()
        usuario_id = cursor.lastrowid
        conn.close()
        return True, usuario_id
    except Exception as e:
        return False, str(e)

def crear_conductor(usuario_id, datos_conductor):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO conductores (
                usuario_id, numero_licencia, categoria_licencia, 
                fecha_vencimiento_licencia, años_experiencia, vehiculo_propio
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            usuario_id,
            datos_conductor['numero_licencia'],
            datos_conductor['categoria_licencia'],
            datos_conductor['fecha_vencimiento_licencia'],
            datos_conductor['años_experiencia'],
            datos_conductor.get('vehiculo_propio', False)
        ))
        
        conn.commit()
        conductor_id = cursor.lastrowid
        conn.close()
        return True, conductor_id
    except Exception as e:
        return False, str(e)

def generar_codigo_solicitud():
    import string
    import random
    codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM solicitudes_servicio WHERE codigo_solicitud = ?', (codigo,))
    if cursor.fetchone():
        conn.close()
        return generar_codigo_solicitud()
    conn.close()
    return codigo

def crear_solicitud_servicio(usuario_id, datos_solicitud):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        codigo_solicitud = generar_codigo_solicitud()
        
        cursor.execute('''
            INSERT INTO solicitudes_servicio (
                codigo_solicitud, usuario_id, tipo_vehiculo, origen, destino,
                fecha_servicio, hora_servicio, numero_pasajeros, telefono_contacto,
                observaciones, precio_estimado
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            codigo_solicitud,
            usuario_id,
            datos_solicitud['tipo_vehiculo'],
            datos_solicitud['origen'],
            datos_solicitud['destino'],
            datos_solicitud['fecha_servicio'],
            datos_solicitud['hora_servicio'],
            datos_solicitud['numero_pasajeros'],
            datos_solicitud['telefono_contacto'],
            datos_solicitud.get('observaciones', ''),
            datos_solicitud.get('precio_estimado', 0)
        ))
        
        conn.commit()
        solicitud_id = cursor.lastrowid
        conn.close()
        
        return True, {
            'solicitud_id': solicitud_id,
            'codigo_solicitud': codigo_solicitud
        }
    except Exception as e:
        return False, str(e)

def obtener_solicitudes_pendientes():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.id, s.codigo_solicitud, s.tipo_vehiculo, s.origen, s.destino,
               s.fecha_servicio, s.hora_servicio, s.numero_pasajeros, s.precio_estimado,
               s.observaciones, s.fecha_solicitud,
               u.nombre, u.apellido, u.telefono
        FROM solicitudes_servicio s
        JOIN usuarios u ON s.usuario_id = u.id
        WHERE s.estado = 'pendiente' AND s.conductor_id IS NULL
        ORDER BY s.fecha_solicitud DESC
    ''')
    solicitudes = cursor.fetchall()
    conn.close()
    return solicitudes

def obtener_solicitudes_conductor(conductor_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.id, s.codigo_solicitud, s.tipo_vehiculo, s.origen, s.destino,
               s.fecha_servicio, s.hora_servicio, s.numero_pasajeros, s.precio_estimado,
               s.precio_final, s.estado, s.fecha_solicitud,
               u.nombre, u.apellido, u.telefono
        FROM solicitudes_servicio s
        JOIN usuarios u ON s.usuario_id = u.id
        WHERE s.conductor_id = ?
        ORDER BY s.fecha_solicitud DESC
    ''', (conductor_id,))
    solicitudes = cursor.fetchall()
    conn.close()
    return solicitudes

def aceptar_solicitud(solicitud_id, conductor_id, precio_final):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE solicitudes_servicio 
            SET conductor_id = ?, precio_final = ?, estado = 'aceptada', fecha_aceptacion = CURRENT_TIMESTAMP
            WHERE id = ? AND estado = 'pendiente'
        ''', (conductor_id, precio_final, solicitud_id))
        
        if cursor.rowcount == 0:
            conn.close()
            return False, "La solicitud ya no está disponible"
        
        conn.commit()
        conn.close()
        return True, "Solicitud aceptada exitosamente"
    except Exception as e:
        return False, str(e)

def obtener_conductor_por_usuario(usuario_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM conductores WHERE usuario_id = ?', (usuario_id,))
    conductor = cursor.fetchone()
    conn.close()
    return conductor

# ==================== RUTAS ====================

@app.route('/')
def inicio():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

@app.route('/login')
def login():
    return render_template('registro-inicio.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    # Verificar tipo de usuario y redirigir al dashboard correspondiente
    if session.get('tipo_usuario') == 'conductor':
        return redirect(url_for('dashboard_conductor'))
    
    return render_template('transporte-mejorado.html')

@app.route('/dashboard-conductor')
def dashboard_conductor():
    if 'usuario_id' not in session or session.get('tipo_usuario') != 'conductor':
        return redirect(url_for('login'))
    return render_template('dashboard-conductor.html')

@app.route('/api/registro', methods=['POST'])
def api_registro():
    try:
        data = request.get_json()
        
        campos_requeridos = ['nombre', 'apellido', 'email', 'telefono', 'cedula', 'password', 'confirm_password', 'tipo_usuario']
        for campo in campos_requeridos:
            if not data.get(campo):
                return jsonify({
                    'success': False,
                    'message': f'El campo {campo} es obligatorio'
                }), 400
        
        if data['password'] != data['confirm_password']:
            return jsonify({
                'success': False,
                'message': 'Las contraseñas no coinciden'
            }), 400
        
        if not validar_email(data['email']):
            return jsonify({
                'success': False,
                'message': 'El formato del email no es válido'
            }), 400
        
        es_valida, mensaje = validar_password(data['password'])
        if not es_valida:
            return jsonify({
                'success': False,
                'message': mensaje
            }), 400
        
        tipo_usuario = data['tipo_usuario']
        if tipo_usuario not in ['pasajero', 'conductor']:
            return jsonify({
                'success': False,
                'message': 'Tipo de usuario inválido'
            }), 400
        
        # Crear usuario
        exito, resultado = crear_usuario(
            data['nombre'].strip(),
            data['apellido'].strip(),
            data['email'].lower().strip(),
            data['telefono'].strip(),
            data['cedula'].strip(),
            data['password'],
            tipo_usuario
        )
        
        if not exito:
            return jsonify({
                'success': False,
                'message': resultado
            }), 400
        
        usuario_id = resultado
        
        # Si es conductor, crear registro adicional
        if tipo_usuario == 'conductor':
            campos_conductor = ['numero_licencia', 'categoria_licencia', 'fecha_vencimiento_licencia', 'años_experiencia']
            for campo in campos_conductor:
                if not data.get(campo):
                    return jsonify({
                        'success': False,
                        'message': f'El campo {campo} es obligatorio para conductores'
                    }), 400
            
            datos_conductor = {
                'numero_licencia': data['numero_licencia'],
                'categoria_licencia': data['categoria_licencia'],
                'fecha_vencimiento_licencia': data['fecha_vencimiento_licencia'],
                'años_experiencia': data['años_experiencia'],
                'vehiculo_propio': data.get('vehiculo_propio', False)
            }
            
            exito_conductor, resultado_conductor = crear_conductor(usuario_id, datos_conductor)
            if not exito_conductor:
                return jsonify({
                    'success': False,
                    'message': f'Usuario creado pero error en datos de conductor: {resultado_conductor}'
                }), 400
        
        return jsonify({
            'success': True,
            'message': 'Usuario registrado exitosamente',
            'usuario_id': usuario_id,
            'tipo_usuario': tipo_usuario
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error interno del servidor'
        }), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        data = request.get_json()
        
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({
                'success': False,
                'message': 'Email y contraseña son obligatorios'
            }), 400
        
        usuario = obtener_usuario_por_email(email)
        
        if not usuario:
            return jsonify({
                'success': False,
                'message': 'Credenciales incorrectas'
            }), 401
        
        if not check_password_hash(usuario[6], password):
            return jsonify({
                'success': False,
                'message': 'Credenciales incorrectas'
            }), 401
        
        # Crear sesión
        session['usuario_id'] = usuario[0]
        session['nombre'] = usuario[1]
        session['apellido'] = usuario[2]
        session['email'] = usuario[3]
        session['tipo_usuario'] = usuario[7]  # tipo_usuario está en la posición 7
        
        return jsonify({
            'success': True,
            'message': 'Inicio de sesión exitoso',
            'usuario': {
                'id': usuario[0],
                'nombre': usuario[1],
                'apellido': usuario[2],
                'email': usuario[3],
                'tipo_usuario': usuario[7]
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error interno del servidor'
        }), 500

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({
        'success': True,
        'message': 'Sesión cerrada exitosamente'
    })

@app.route('/api/usuario', methods=['GET'])
def api_usuario():
    if 'usuario_id' not in session:
        return jsonify({
            'success': False,
            'message': 'No hay sesión activa'
        }), 401
    
    return jsonify({
        'success': True,
        'usuario': {
            'id': session['usuario_id'],
            'nombre': session['nombre'],
            'apellido': session['apellido'],
            'email': session['email'],
            'tipo_usuario': session.get('tipo_usuario', 'pasajero')
        }
    })

@app.route('/api/solicitud-servicio', methods=['POST'])
def api_solicitud_servicio():
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        
        campos_requeridos = ['tipo_vehiculo', 'origen', 'destino', 'fecha_servicio', 'hora_servicio', 'numero_pasajeros', 'telefono_contacto']
        for campo in campos_requeridos:
            if not data.get(campo):
                return jsonify({
                    'success': False,
                    'message': f'El campo {campo} es obligatorio'
                }), 400
        
        exito, resultado = crear_solicitud_servicio(session['usuario_id'], data)
        
        if exito:
            return jsonify({
                'success': True,
                'message': 'Solicitud creada exitosamente',
                'solicitud': resultado
            })
        else:
            return jsonify({
                'success': False,
                'message': resultado
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error interno del servidor'
        }), 500

@app.route('/api/solicitudes-pendientes', methods=['GET'])
def api_solicitudes_pendientes():
    if 'usuario_id' not in session or session.get('tipo_usuario') != 'conductor':
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        solicitudes = obtener_solicitudes_pendientes()
        
        solicitudes_list = []
        for s in solicitudes:
            solicitudes_list.append({
                'id': s[0],
                'codigo_solicitud': s[1],
                'tipo_vehiculo': s[2],
                'origen': s[3],
                'destino': s[4],
                'fecha_servicio': s[5],
                'hora_servicio': s[6],
                'numero_pasajeros': s[7],
                'precio_estimado': s[8],
                'observaciones': s[9],
                'fecha_solicitud': s[10],
                'cliente_nombre': f"{s[11]} {s[12]}",
                'cliente_telefono': s[13]
            })
        
        return jsonify({
            'success': True,
            'solicitudes': solicitudes_list
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error obteniendo solicitudes'
        }), 500

@app.route('/api/mis-solicitudes-conductor', methods=['GET'])
def api_mis_solicitudes_conductor():
    if 'usuario_id' not in session or session.get('tipo_usuario') != 'conductor':
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        conductor = obtener_conductor_por_usuario(session['usuario_id'])
        if not conductor:
            return jsonify({
                'success': False,
                'message': 'Conductor no encontrado'
            }), 404
        
        solicitudes = obtener_solicitudes_conductor(conductor[0])
        
        solicitudes_list = []
        for s in solicitudes:
            solicitudes_list.append({
                'id': s[0],
                'codigo_solicitud': s[1],
                'tipo_vehiculo': s[2],
                'origen': s[3],
                'destino': s[4],
                'fecha_servicio': s[5],
                'hora_servicio': s[6],
                'numero_pasajeros': s[7],
                'precio_estimado': s[8],
                'precio_final': s[9],
                'estado': s[10],
                'fecha_solicitud': s[11],
                'cliente_nombre': f"{s[12]} {s[13]}",
                'cliente_telefono': s[14]
            })
        
        return jsonify({
            'success': True,
            'solicitudes': solicitudes_list
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error obteniendo solicitudes'
        }), 500

@app.route('/api/aceptar-solicitud', methods=['POST'])
def api_aceptar_solicitud():
    if 'usuario_id' not in session or session.get('tipo_usuario') != 'conductor':
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        
        if not data.get('solicitud_id') or not data.get('precio_final'):
            return jsonify({
                'success': False,
                'message': 'Faltan datos requeridos'
            }), 400
        
        conductor = obtener_conductor_por_usuario(session['usuario_id'])
        if not conductor:
            return jsonify({
                'success': False,
                'message': 'Conductor no encontrado'
            }), 404
        
        exito, mensaje = aceptar_solicitud(
            data['solicitud_id'],
            conductor[0],
            data['precio_final']
        )
        
        if exito:
            return jsonify({
                'success': True,
                'message': mensaje
            })
        else:
            return jsonify({
                'success': False,
                'message': mensaje
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error procesando solicitud'
        }), 500

@app.route('/api/crear-solicitud-prueba', methods=['POST'])
def crear_solicitud_prueba():
    """Crea solicitudes de prueba para testing"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Obtener un usuario pasajero para las solicitudes
        cursor.execute("SELECT id FROM usuarios WHERE tipo_usuario = 'pasajero' LIMIT 1")
        pasajero = cursor.fetchone()
        
        if not pasajero:
            conn.close()
            return jsonify({'success': False, 'message': 'No hay usuarios pasajeros'}), 400
        
        pasajero_id = pasajero[0]
        
        # Crear 3 solicitudes de prueba
        solicitudes_prueba = [
            ('PRUEBA01', pasajero_id, 'carro', 'Quibdó', 'Tadó', '2025-10-15', '08:00', 3, '3001234567', 'Solicitud de prueba 1', 18000),
            ('PRUEBA02', pasajero_id, 'moto', 'Centro', 'Kennedy', '2025-10-15', '10:00', 1, '3001234568', 'Solicitud de prueba 2', 5000),
            ('PRUEBA03', pasajero_id, 'bus', 'Quibdó', 'Pereira', '2025-10-16', '07:00', 20, '3001234569', 'Solicitud de prueba 3', 45000),
        ]
        
        for sol in solicitudes_prueba:
            try:
                cursor.execute('''
                    INSERT INTO solicitudes_servicio (
                        codigo_solicitud, usuario_id, tipo_vehiculo, origen, destino,
                        fecha_servicio, hora_servicio, numero_pasajeros, telefono_contacto,
                        observaciones, precio_estimado, estado
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente')
                ''', sol)
            except sqlite3.IntegrityError:
                # Si ya existe, continuar con la siguiente
                continue
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Solicitudes de prueba creadas'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/debug/solicitudes', methods=['GET'])
def debug_solicitudes():
    """Ruta de debug para ver todas las solicitudes"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Ver TODAS las solicitudes
        cursor.execute('''
            SELECT s.id, s.codigo_solicitud, s.tipo_vehiculo, s.origen, s.destino,
                   s.estado, s.conductor_id, s.usuario_id,
                   u.nombre, u.apellido
            FROM solicitudes_servicio s
            JOIN usuarios u ON s.usuario_id = u.id
            ORDER BY s.fecha_solicitud DESC
        ''')
        todas = cursor.fetchall()
        
        # Ver solicitudes pendientes sin conductor
        cursor.execute('''
            SELECT s.id, s.codigo_solicitud, s.tipo_vehiculo, s.origen, s.destino,
                   s.estado, s.conductor_id
            FROM solicitudes_servicio s
            WHERE s.estado = 'pendiente' AND s.conductor_id IS NULL
        ''')
        pendientes = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'total_solicitudes': len(todas),
            'solicitudes_pendientes': len(pendientes),
            'todas': [{'id': s[0], 'codigo': s[1], 'tipo': s[2], 'origen': s[3], 
                      'destino': s[4], 'estado': s[5], 'conductor_id': s[6], 
                      'usuario_id': s[7], 'usuario': f"{s[8]} {s[9]}"} for s in todas],
            'pendientes': [{'id': s[0], 'codigo': s[1], 'tipo': s[2], 'origen': s[3], 
                           'destino': s[4], 'estado': s[5], 'conductor_id': s[6]} for s in pendientes]
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/perfil')
def perfil():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    return render_template('perfil.html')


@app.route('/rutas')
def rutas():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    return render_template('rutas.html')

# Agregar estas rutas al archivo auth_server.py (antes de if __name__ == '__main__':)

@app.route('/api/rutas', methods=['GET'])
def api_rutas():
    """Obtiene todas las rutas disponibles"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, origen, destino, distancia_km, duracion_horas, 
                   precio_base, tipo_ruta, descripcion, activa
            FROM rutas
            WHERE activa = 1
            ORDER BY origen, destino
        ''')
        
        rutas = cursor.fetchall()
        conn.close()
        
        rutas_list = []
        for r in rutas:
            rutas_list.append({
                'id': r[0],
                'origen': r[1],
                'destino': r[2],
                'distancia_km': r[3],
                'duracion_horas': r[4],
                'precio_base': r[5],
                'tipo_ruta': r[6],
                'descripcion': r[7],
                'activa': r[8]
            })
        
        return jsonify({
            'success': True,
            'rutas': rutas_list
        })
    except Exception as e:
        print(f"Error obteniendo rutas: {e}")
        return jsonify({
            'success': False,
            'message': 'Error obteniendo rutas'
        }), 500

@app.route('/api/horarios/<int:ruta_id>', methods=['GET'])
def api_horarios(ruta_id):
    """Obtiene los horarios disponibles para una ruta específica"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        fecha = request.args.get('fecha')
        if not fecha:
            return jsonify({
                'success': False,
                'message': 'Fecha es requerida'
            }), 400
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Obtener información de la ruta
        cursor.execute('SELECT origen, destino, duracion_horas FROM rutas WHERE id = ?', (ruta_id,))
        ruta = cursor.fetchone()
        
        if not ruta:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Ruta no encontrada'
            }), 404
        
        # Obtener horarios disponibles
        cursor.execute('''
            SELECT h.id, h.fecha_salida, h.fecha_llegada, h.precio, 
                   h.asientos_disponibles, h.estado,
                   v.placa, v.tipo_vehiculo, v.marca, v.modelo
            FROM horarios h
            JOIN vehiculos v ON h.vehiculo_id = v.id
            WHERE h.ruta_id = ? 
            AND DATE(h.fecha_salida) = ?
            AND h.estado = 'programado'
            AND h.asientos_disponibles > 0
            ORDER BY h.fecha_salida
        ''', (ruta_id, fecha))
        
        horarios = cursor.fetchall()
        conn.close()
        
        horarios_list = []
        for h in horarios:
            horarios_list.append({
                'id': h[0],
                'fecha_salida': h[1],
                'fecha_llegada': h[2],
                'precio': h[3],
                'asientos_disponibles': h[4],
                'estado': h[5],
                'placa': h[6],
                'tipo_vehiculo': h[7],
                'marca': h[8],
                'modelo': h[9],
                'origen': ruta[0],
                'destino': ruta[1],
                'duracion_horas': ruta[2]
            })
        
        return jsonify({
            'success': True,
            'horarios': horarios_list
        })
    except Exception as e:
        print(f"Error obteniendo horarios: {e}")
        return jsonify({
            'success': False,
            'message': 'Error obteniendo horarios'
        }), 500

@app.route('/servicios')
def servicios():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    return render_template('servicios.html')

@app.route('/nosotros')
def nosotros():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    return render_template('nosotros.html')

@app.route('/reservar')
def reservar():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    return render_template('reservas.html')

@app.route('/mis-reservas')
def mis_reservas():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    return render_template('mis-reservas.html')

# Agregar esta función al archivo auth_server.py

def obtener_solicitudes_usuario(usuario_id):
    """Obtiene todas las solicitudes de un usuario pasajero"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.id, s.codigo_solicitud, s.tipo_vehiculo, s.origen, s.destino,
               s.fecha_servicio, s.hora_servicio, s.numero_pasajeros, 
               s.precio_estimado, s.precio_final, s.estado, s.fecha_solicitud,
               s.observaciones, s.telefono_contacto,
               c.usuario_id as conductor_usuario_id,
               u.nombre as conductor_nombre, u.apellido as conductor_apellido, 
               u.telefono as conductor_telefono
        FROM solicitudes_servicio s
        LEFT JOIN conductores c ON s.conductor_id = c.id
        LEFT JOIN usuarios u ON c.usuario_id = u.id
        WHERE s.usuario_id = ?
        ORDER BY s.fecha_solicitud DESC
    ''', (usuario_id,))
    solicitudes = cursor.fetchall()
    conn.close()
    return solicitudes

# Agregar esta ruta al archivo auth_server.py
@app.route('/api/mis-solicitudes', methods=['GET'])
def api_mis_solicitudes():
    """Obtiene las solicitudes del pasajero autenticado"""
    if 'usuario_id' not in session or session.get('tipo_usuario') != 'pasajero':
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        solicitudes = obtener_solicitudes_usuario(session['usuario_id'])
        
        solicitudes_list = []
        for s in solicitudes:
            solicitud_data = {
                'id': s[0],
                'codigo_solicitud': s[1],
                'tipo_vehiculo': s[2],
                'origen': s[3],
                'destino': s[4],
                'fecha_servicio': s[5],
                'hora_servicio': s[6],
                'numero_pasajeros': s[7],
                'precio_estimado': s[8],
                'precio_final': s[9],
                'estado': s[10],
                'fecha_solicitud': s[11],
                'observaciones': s[12],
                'telefono_contacto': s[13]
            }
            
            
            if s[14]: 
                solicitud_data['conductor'] = {
                    'nombre': f"{s[15]} {s[16]}",
                    'telefono': s[17]
                }
            
            solicitudes_list.append(solicitud_data)
        
        return jsonify({
            'success': True,
            'solicitudes': solicitudes_list
        })
    except Exception as e:
        print(f"Error obteniendo solicitudes: {e}")
        return jsonify({
            'success': False,
            'message': 'Error obteniendo solicitudes'
        }), 500

@app.route('/mis-viajes')
def mis_viajes():
    if 'usuario_id' not in session or session.get('tipo_usuario') != 'pasajero':
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    viajes = []

    try:
        cursor.execute('''
            SELECT codigo_solicitud, origen, destino, fecha_servicio, hora_servicio,
                   tipo_vehiculo, precio_estimado, precio_final, estado
            FROM solicitudes_servicio
            WHERE usuario_id = ?
            ORDER BY fecha_servicio DESC
        ''', (session['usuario_id'],))
        for r in cursor.fetchall():
            viajes.append({
                'codigo_solicitud': r[0],
                'origen': r[1],
                'destino': r[2],
                'fecha_servicio': r[3],
                'hora_servicio': r[4],
                'tipo_vehiculo': r[5],
                'precio_estimado': r[6],
                'precio_final': r[7],
                'estado': r[8]
            })
    finally:
        conn.close()

    return render_template('mis-viajes.html', viajes=viajes)




if __name__ == '__main__':
    init_db() 



    
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    print("✓ Servidor iniciado en http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)