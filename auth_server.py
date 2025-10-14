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
    
    # Verificar si la tabla usuarios existe y tiene la restricción correcta
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='usuarios'")
    result = cursor.fetchone()
    
    # Si existe pero no tiene 'administrador' en el CHECK, eliminarla
    if result and 'administrador' not in result[0]:
        print("⚠️  Recreando tabla usuarios con restricción correcta...")
        cursor.execute('DROP TABLE IF EXISTS usuarios')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            telefono TEXT NOT NULL,
            cedula TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            tipo_usuario TEXT CHECK(tipo_usuario IN ('pasajero', 'conductor', 'administrador')) DEFAULT 'pasajero',
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ultimo_acceso TIMESTAMP
        )
    ''')
    
    # Tabla para mensajes del chat (soporte)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensajes_soporte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            mensaje TEXT NOT NULL,
            tipo TEXT CHECK(tipo IN ('consulta', 'queja', 'sugerencia', 'otro')) DEFAULT 'consulta',
            estado TEXT CHECK(estado IN ('pendiente', 'en_proceso', 'resuelto')) DEFAULT 'pendiente',
            prioridad TEXT CHECK(prioridad IN ('baja', 'media', 'alta', 'urgente')) DEFAULT 'media',
            respuesta TEXT,
            admin_id INTEGER,
            fecha_mensaje TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_respuesta TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
            FOREIGN KEY (admin_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Tabla para notificaciones de administradores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notificaciones_admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            mensaje_id INTEGER NOT NULL,
            leida BOOLEAN DEFAULT FALSE,
            fecha_notificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (admin_id) REFERENCES usuarios (id),
            FOREIGN KEY (mensaje_id) REFERENCES mensajes_soporte (id)
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
    
def actualizar_db_conversaciones():
    """Actualiza la base de datos con las nuevas tablas para conversaciones"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Tabla de conversaciones (hilos de chat)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            admin_id INTEGER,
            asunto TEXT NOT NULL,
            tipo TEXT CHECK(tipo IN ('consulta', 'queja', 'sugerencia', 'otro')) DEFAULT 'consulta',
            estado TEXT CHECK(estado IN ('abierta', 'en_proceso', 'cerrada')) DEFAULT 'abierta',
            prioridad TEXT CHECK(prioridad IN ('baja', 'media', 'alta', 'urgente')) DEFAULT 'media',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_ultima_actividad TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_cierre TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
            FOREIGN KEY (admin_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Tabla de mensajes de conversación
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensajes_conversacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversacion_id INTEGER NOT NULL,
            remitente_id INTEGER NOT NULL,
            mensaje TEXT NOT NULL,
            leido BOOLEAN DEFAULT FALSE,
            fecha_mensaje TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversacion_id) REFERENCES conversaciones (id),
            FOREIGN KEY (remitente_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Tabla de participantes en conversaciones
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participantes_conversacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversacion_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            mensajes_no_leidos INTEGER DEFAULT 0,
            ultima_lectura TIMESTAMP,
            FOREIGN KEY (conversacion_id) REFERENCES conversaciones (id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
            UNIQUE(conversacion_id, usuario_id)
        )
    ''')


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

def crear_administrador(nombre, apellido, email, telefono, cedula, password):
    """Crea un usuario administrador"""
    return crear_usuario(nombre, apellido, email, telefono, cedula, password, tipo_usuario='administrador')

@app.route('/api/registro-admin', methods=['POST'])
def api_registro_admin():
    """Registra un nuevo administrador - Solo accesible por admin"""
    if 'usuario_id' not in session or session.get('tipo_usuario') != 'administrador':
        return jsonify({
            'success': False,
            'message': 'Solo administradores pueden crear nuevos administradores'
        }), 403
    
    try:
        data = request.get_json()
        
        campos_requeridos = ['nombre', 'apellido', 'email', 'telefono', 'cedula', 'password', 'confirm_password']
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
        
        exito, resultado = crear_administrador(
            data['nombre'].strip(),
            data['apellido'].strip(),
            data['email'].lower().strip(),
            data['telefono'].strip(),
            data['cedula'].strip(),
            data['password']
        )
        
        if not exito:
            return jsonify({
                'success': False,
                'message': resultado
            }), 400
        
        return jsonify({
            'success': True,
            'message': 'Administrador registrado exitosamente',
            'usuario_id': resultado
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error interno del servidor'
        }), 500

@app.route('/api/guardar-mensaje-chat', methods=['POST'])
def api_guardar_mensaje_chat():
    """Guarda un mensaje del chat como ticket de soporte"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        
        if not data.get('mensaje'):
            return jsonify({
                'success': False,
                'message': 'El mensaje es obligatorio'
            }), 400
        
        mensaje_lower = data['mensaje'].lower()
        tipo = 'consulta'
        prioridad = 'media'
        
        if any(palabra in mensaje_lower for palabra in ['queja', 'reclamo', 'problema', 'mal', 'pésimo', 'molesto', 'terrible']):
            tipo = 'queja'
            prioridad = 'alta'
        elif any(palabra in mensaje_lower for palabra in ['sugerencia', 'mejorar', 'propuesta', 'recomiendo']):
            tipo = 'sugerencia'
            prioridad = 'baja'
        elif any(palabra in mensaje_lower for palabra in ['urgente', 'emergencia', 'ayuda', 'importante']):
            prioridad = 'urgente'
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO mensajes_soporte (usuario_id, mensaje, tipo, prioridad)
            VALUES (?, ?, ?, ?)
        ''', (session['usuario_id'], data['mensaje'], tipo, prioridad))
        
        mensaje_id = cursor.lastrowid
        
        cursor.execute('SELECT id FROM usuarios WHERE tipo_usuario = "administrador"')
        admins = cursor.fetchall()
        
        for admin in admins:
            cursor.execute('''
                INSERT INTO notificaciones_admin (admin_id, mensaje_id)
                VALUES (?, ?)
            ''', (admin[0], mensaje_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message_id': mensaje_id,
            'tipo': tipo,
            'prioridad': prioridad,
            'respuesta': '✅ Tu mensaje ha sido recibido. Un agente te responderá pronto.'
        })
        
    except Exception as e:
        print(f"Error guardando mensaje: {e}")
        return jsonify({
            'success': False,
            'message': 'Error guardando mensaje'
        }), 500

@app.route('/api/mensajes-soporte', methods=['GET'])
def api_mensajes_soporte():
    """Obtiene todos los mensajes de soporte - Solo para administradores"""
    if 'usuario_id' not in session or session.get('tipo_usuario') != 'administrador':
        return jsonify({'success': False, 'message': 'No autorizado'}), 403
    
    try:
        estado = request.args.get('estado', 'todos')
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        if estado == 'todos':
            cursor.execute('''
                SELECT m.id, m.mensaje, m.tipo, m.estado, m.prioridad, 
                       m.fecha_mensaje, m.respuesta, m.fecha_respuesta,
                       u.nombre, u.apellido, u.email, u.telefono
                FROM mensajes_soporte m
                JOIN usuarios u ON m.usuario_id = u.id
                ORDER BY 
                    CASE m.prioridad
                        WHEN 'urgente' THEN 1
                        WHEN 'alta' THEN 2
                        WHEN 'media' THEN 3
                        WHEN 'baja' THEN 4
                    END,
                    m.fecha_mensaje DESC
            ''')
        else:
            cursor.execute('''
                SELECT m.id, m.mensaje, m.tipo, m.estado, m.prioridad, 
                       m.fecha_mensaje, m.respuesta, m.fecha_respuesta,
                       u.nombre, u.apellido, u.email, u.telefono
                FROM mensajes_soporte m
                JOIN usuarios u ON m.usuario_id = u.id
                WHERE m.estado = ?
                ORDER BY 
                    CASE m.prioridad
                        WHEN 'urgente' THEN 1
                        WHEN 'alta' THEN 2
                        WHEN 'media' THEN 3
                        WHEN 'baja' THEN 4
                    END,
                    m.fecha_mensaje DESC
            ''', (estado,))
        
        mensajes = cursor.fetchall()
        conn.close()
        
        mensajes_list = []
        for m in mensajes:
            mensajes_list.append({
                'id': m[0],
                'mensaje': m[1],
                'tipo': m[2],
                'estado': m[3],
                'prioridad': m[4],
                'fecha_mensaje': m[5],
                'respuesta': m[6],
                'fecha_respuesta': m[7],
                'usuario': {
                    'nombre': f"{m[8]} {m[9]}",
                    'email': m[10],
                    'telefono': m[11]
                }
            })
        
        return jsonify({
            'success': True,
            'mensajes': mensajes_list
        })
        
    except Exception as e:
        print(f"Error obteniendo mensajes: {e}")
        return jsonify({
            'success': False,
            'message': 'Error obteniendo mensajes'
        }), 500

@app.route('/api/responder-mensaje', methods=['POST'])
def api_responder_mensaje():
    """Responde a un mensaje de soporte - Solo para administradores"""
    if 'usuario_id' not in session or session.get('tipo_usuario') != 'administrador':
        return jsonify({'success': False, 'message': 'No autorizado'}), 403
    
    try:
        data = request.get_json()
        
        if not data.get('mensaje_id') or not data.get('respuesta'):
            return jsonify({
                'success': False,
                'message': 'Mensaje ID y respuesta son obligatorios'
            }), 400
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE mensajes_soporte
            SET respuesta = ?, admin_id = ?, fecha_respuesta = CURRENT_TIMESTAMP, estado = 'resuelto'
            WHERE id = ?
        ''', (data['respuesta'], session['usuario_id'], data['mensaje_id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Respuesta enviada exitosamente'
        })
        
    except Exception as e:
        print(f"Error respondiendo mensaje: {e}")
        return jsonify({
            'success': False,
            'message': 'Error enviando respuesta'
        }), 500

@app.route('/api/notificaciones-admin', methods=['GET'])
def api_notificaciones_admin():
    """Obtiene notificaciones pendientes del administrador"""
    if 'usuario_id' not in session or session.get('tipo_usuario') != 'administrador':
        return jsonify({'success': False, 'message': 'No autorizado'}), 403
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) 
            FROM notificaciones_admin 
            WHERE admin_id = ? AND leida = 0
        ''', (session['usuario_id'],))
        
        no_leidas = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            'success': True,
            'notificaciones_pendientes': no_leidas
        })
        
    except Exception as e:
        print(f"Error obteniendo notificaciones: {e}")
        return jsonify({
            'success': False,
            'message': 'Error obteniendo notificaciones'
        }), 500

@app.route('/api/marcar-notificaciones-leidas', methods=['POST'])
def api_marcar_notificaciones_leidas():
    """Marca todas las notificaciones como leídas"""
    if 'usuario_id' not in session or session.get('tipo_usuario') != 'administrador':
        return jsonify({'success': False, 'message': 'No autorizado'}), 403
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE notificaciones_admin
            SET leida = 1
            WHERE admin_id = ?
        ''', (session['usuario_id'],))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Notificaciones marcadas como leídas'
        })
        
    except Exception as e:
        print(f"Error marcando notificaciones: {e}")
        return jsonify({
            'success': False,
            'message': 'Error marcando notificaciones'
        }), 500

def crear_primer_admin():
    """Crea el primer administrador del sistema"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM usuarios WHERE tipo_usuario = "administrador"')
    if cursor.fetchone()[0] > 0:
        conn.close()
        return
    
    password_hash = generate_password_hash('Admin123!')
    
    cursor.execute('''
        INSERT INTO usuarios (nombre, apellido, email, telefono, cedula, password_hash, tipo_usuario)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', ('Admin', 'Sistema', 'admin@transporteaguila.com', '3001234567', '00000000', password_hash, 'administrador'))
    
    conn.commit()
    conn.close()
    
    print("✓ Administrador creado:")
    print("  Email: admin@transporteaguila.com")
    print("  Contraseña: Admin123!")

@app.route('/dashboard-admin')
def dashboard_admin():
    if 'usuario_id' not in session or session.get('tipo_usuario') != 'administrador':
        return redirect(url_for('login'))
    return render_template('dashboard-admin.html')

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
    
    tipo = session.get('tipo_usuario')

    if tipo == 'conductor':
        return redirect(url_for('dashboard_conductor'))
    elif tipo == 'administrador':
        return redirect(url_for('dashboard_admin'))

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
        
        session['usuario_id'] = usuario[0]
        session['nombre'] = usuario[1]
        session['apellido'] = usuario[2]
        session['email'] = usuario[3]
        session['tipo_usuario'] = usuario[7]
        
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
        
        cursor.execute("SELECT id FROM usuarios WHERE tipo_usuario = 'pasajero' LIMIT 1")
        pasajero = cursor.fetchone()
        
        if not pasajero:
            conn.close()
            return jsonify({'success': False, 'message': 'No hay usuarios pasajeros'}), 400
        
        pasajero_id = pasajero[0]
        
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
        
        cursor.execute('''
            SELECT s.id, s.codigo_solicitud, s.tipo_vehiculo, s.origen, s.destino,
                   s.estado, s.conductor_id, s.usuario_id,
                   u.nombre, u.apellido
            FROM solicitudes_servicio s
            JOIN usuarios u ON s.usuario_id = u.id
            ORDER BY s.fecha_solicitud DESC
        ''')
        todas = cursor.fetchall()
        
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
        
        cursor.execute('SELECT origen, destino, duracion_horas FROM rutas WHERE id = ?', (ruta_id,))
        ruta = cursor.fetchone()
        
        if not ruta:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Ruta no encontrada'
            }), 404
        
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

def generar_codigo_reserva():
    import string
    import random
    codigo = 'RES-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM reservas WHERE codigo_reserva = ?', (codigo,))
    if cursor.fetchone():
        conn.close()
        return generar_codigo_reserva()
    conn.close()
    return codigo

@app.route('/api/rutas', methods=['GET'])
def api_rutas():
    """Obtiene todas las rutas disponibles"""
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

@app.route('/api/reservar', methods=['POST'])
def api_reservar():
    """Crea una nueva reserva"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        
        campos_requeridos = ['horario_id', 'nombre', 'cedula', 'telefono', 'email']
        for campo in campos_requeridos:
            if not data.get(campo):
                return jsonify({
                    'success': False,
                    'message': f'El campo {campo} es obligatorio'
                }), 400
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT asientos_disponibles, precio 
            FROM horarios 
            WHERE id = ? AND estado = 'programado'
        ''', (data['horario_id'],))
        
        horario = cursor.fetchone()
        
        if not horario:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Horario no disponible'
            }), 400
        
        if horario[0] <= 0:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'No hay asientos disponibles'
            }), 400
        
        codigo_reserva = generar_codigo_reserva()
        
        from datetime import datetime, timedelta
        fecha_vencimiento = datetime.now() + timedelta(hours=2)
        
        cursor.execute('''
            INSERT INTO reservas (
                codigo_reserva, usuario_id, horario_id, nombre_pasajero,
                cedula_pasajero, telefono_pasajero, email_pasajero,
                precio_total, estado, fecha_vencimiento, notas
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?)
        ''', (
            codigo_reserva,
            session['usuario_id'],
            data['horario_id'],
            data['nombre'],
            data['cedula'],
            data['telefono'],
            data['email'],
            horario[1],
            fecha_vencimiento.strftime('%Y-%m-%d %H:%M:%S'),
            data.get('notas', '')
        ))
        
        cursor.execute('''
            UPDATE horarios 
            SET asientos_disponibles = asientos_disponibles - 1
            WHERE id = ?
        ''', (data['horario_id'],))
        
        conn.commit()
        reserva_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'success': True,
            'reserva': {
                'id': reserva_id,
                'codigo_reserva': codigo_reserva,
                'fecha_vencimiento': fecha_vencimiento.strftime('%Y-%m-%d %H:%M:%S')
            },
            'message': 'Reserva creada exitosamente'
        })
        
    except Exception as e:
        print(f"Error creando reserva: {e}")
        return jsonify({
            'success': False,
            'message': 'Error procesando la reserva'
        }), 500

@app.route('/api/iniciar-conversacion', methods=['POST'])
def api_iniciar_conversacion():
    """Inicia una nueva conversación desde el chat"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        
        if not data.get('mensaje'):
            return jsonify({
                'success': False,
                'message': 'El mensaje es obligatorio'
            }), 400
        
        # Detectar tipo y prioridad automáticamente
        mensaje_lower = data['mensaje'].lower()
        tipo = 'consulta'
        prioridad = 'media'
        
        if any(palabra in mensaje_lower for palabra in ['queja', 'reclamo', 'problema', 'mal', 'pésimo']):
            tipo = 'queja'
            prioridad = 'alta'
        elif any(palabra in mensaje_lower for palabra in ['sugerencia', 'mejorar', 'propuesta']):
            tipo = 'sugerencia'
            prioridad = 'baja'
        elif any(palabra in mensaje_lower for palabra in ['urgente', 'emergencia', 'ayuda']):
            prioridad = 'urgente'
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Crear la conversación
        cursor.execute('''
            INSERT INTO conversaciones (usuario_id, asunto, tipo, prioridad)
            VALUES (?, ?, ?, ?)
        ''', (session['usuario_id'], data['mensaje'][:100], tipo, prioridad))
        
        conversacion_id = cursor.lastrowid
        
        # Insertar el primer mensaje
        cursor.execute('''
            INSERT INTO mensajes_conversacion (conversacion_id, remitente_id, mensaje)
            VALUES (?, ?, ?)
        ''', (conversacion_id, session['usuario_id'], data['mensaje']))
        
        # Agregar usuario como participante
        cursor.execute('''
            INSERT INTO participantes_conversacion (conversacion_id, usuario_id, ultima_lectura)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (conversacion_id, session['usuario_id']))
        
        # Notificar a todos los administradores
        cursor.execute('SELECT id FROM usuarios WHERE tipo_usuario = "administrador"')
        admins = cursor.fetchall()
        
        for admin in admins:
            cursor.execute('''
                INSERT OR IGNORE INTO participantes_conversacion 
                (conversacion_id, usuario_id, mensajes_no_leidos)
                VALUES (?, ?, 1)
            ''', (conversacion_id, admin[0]))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'conversacion_id': conversacion_id,
            'message': 'Conversación iniciada. Un agente te responderá pronto.'
        })
        
    except Exception as e:
        print(f"Error iniciando conversación: {e}")
        return jsonify({
            'success': False,
            'message': 'Error iniciando conversación'
        }), 500

@app.route('/api/enviar-mensaje-conversacion', methods=['POST'])
def api_enviar_mensaje_conversacion():
    """Envía un mensaje en una conversación existente"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        
        if not data.get('conversacion_id') or not data.get('mensaje'):
            return jsonify({
                'success': False,
                'message': 'Conversación ID y mensaje son obligatorios'
            }), 400
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Verificar que el usuario sea parte de la conversación
        cursor.execute('''
            SELECT c.usuario_id, c.admin_id, c.estado
            FROM conversaciones c
            WHERE c.id = ?
        ''', (data['conversacion_id'],))
        
        conv = cursor.fetchone()
        
        if not conv:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Conversación no encontrada'
            }), 404
        
        # Verificar permisos
        es_admin = session.get('tipo_usuario') == 'administrador'
        es_usuario_original = conv[0] == session['usuario_id']
        es_admin_asignado = conv[1] == session['usuario_id']
        
        if not (es_admin or es_usuario_original or es_admin_asignado):
            conn.close()
            return jsonify({
                'success': False,
                'message': 'No tienes permiso para enviar mensajes en esta conversación'
            }), 403
        
        # Si la conversación está cerrada, reabrirla
        if conv[2] == 'cerrada':
            cursor.execute('''
                UPDATE conversaciones
                SET estado = 'abierta', fecha_ultima_actividad = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (data['conversacion_id'],))
        
        # Insertar el mensaje
        cursor.execute('''
            INSERT INTO mensajes_conversacion (conversacion_id, remitente_id, mensaje)
            VALUES (?, ?, ?)
        ''', (data['conversacion_id'], session['usuario_id'], data['mensaje']))
        
        # Actualizar fecha de última actividad
        cursor.execute('''
            UPDATE conversaciones
            SET fecha_ultima_actividad = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (data['conversacion_id'],))
        
        # Asignar admin si es la primera respuesta de un admin
        if es_admin and not conv[1]:
            cursor.execute('''
                UPDATE conversaciones
                SET admin_id = ?, estado = 'en_proceso'
                WHERE id = ?
            ''', (session['usuario_id'], data['conversacion_id']))
        
        # Marcar mensajes no leídos para otros participantes
        cursor.execute('''
            UPDATE participantes_conversacion
            SET mensajes_no_leidos = mensajes_no_leidos + 1
            WHERE conversacion_id = ? AND usuario_id != ?
        ''', (data['conversacion_id'], session['usuario_id']))
        
        # Actualizar última lectura del remitente
        cursor.execute('''
            UPDATE participantes_conversacion
            SET ultima_lectura = CURRENT_TIMESTAMP, mensajes_no_leidos = 0
            WHERE conversacion_id = ? AND usuario_id = ?
        ''', (data['conversacion_id'], session['usuario_id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Mensaje enviado exitosamente'
        })
        
    except Exception as e:
        print(f"Error enviando mensaje: {e}")
        return jsonify({
            'success': False,
            'message': 'Error enviando mensaje'
        }), 500


@app.route('/api/mis-conversaciones', methods=['GET'])
def api_mis_conversaciones():
    """Obtiene todas las conversaciones del usuario"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        es_admin = session.get('tipo_usuario') == 'administrador'
        
        if es_admin:
            # Admins ven todas las conversaciones
            cursor.execute('''
                SELECT c.id, c.asunto, c.tipo, c.estado, c.prioridad,
                       c.fecha_creacion, c.fecha_ultima_actividad,
                       u.nombre, u.apellido,
                       p.mensajes_no_leidos,
                       (SELECT COUNT(*) FROM mensajes_conversacion WHERE conversacion_id = c.id) as total_mensajes
                FROM conversaciones c
                JOIN usuarios u ON c.usuario_id = u.id
                LEFT JOIN participantes_conversacion p ON c.id = p.conversacion_id AND p.usuario_id = ?
                ORDER BY c.fecha_ultima_actividad DESC
            ''', (session['usuario_id'],))
        else:
            # Usuarios ven solo sus conversaciones
            cursor.execute('''
                SELECT c.id, c.asunto, c.tipo, c.estado, c.prioridad,
                       c.fecha_creacion, c.fecha_ultima_actividad,
                       a.nombre, a.apellido,
                       p.mensajes_no_leidos,
                       (SELECT COUNT(*) FROM mensajes_conversacion WHERE conversacion_id = c.id) as total_mensajes
                FROM conversaciones c
                LEFT JOIN usuarios a ON c.admin_id = a.id
                LEFT JOIN participantes_conversacion p ON c.id = p.conversacion_id AND p.usuario_id = ?
                WHERE c.usuario_id = ?
                ORDER BY c.fecha_ultima_actividad DESC
            ''', (session['usuario_id'], session['usuario_id']))
        
        conversaciones = cursor.fetchall()
        conn.close()
        
        conversaciones_list = []
        for c in conversaciones:
            conversaciones_list.append({
                'id': c[0],
                'asunto': c[1],
                'tipo': c[2],
                'estado': c[3],
                'prioridad': c[4],
                'fecha_creacion': c[5],
                'fecha_ultima_actividad': c[6],
                'otro_participante': f"{c[7]} {c[8]}" if c[7] else 'Sin asignar',
                'mensajes_no_leidos': c[9] or 0,
                'total_mensajes': c[10]
            })
        
        return jsonify({
            'success': True,
            'conversaciones': conversaciones_list
        })
        
    except Exception as e:
        print(f"Error obteniendo conversaciones: {e}")
        return jsonify({
            'success': False,
            'message': 'Error obteniendo conversaciones'
        }), 500
# Ruta para obtener mis reservas
@app.route('/api/mis-reservas', methods=['GET'])
def api_mis_reservas():
    """Obtiene las reservas del usuario autenticado"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT r.id, r.codigo_reserva, r.nombre_pasajero, r.cedula_pasajero,
                   r.telefono_pasajero, r.precio_total, r.estado, r.fecha_reserva,
                   r.fecha_vencimiento, r.notas,
                   h.fecha_salida, h.fecha_llegada,
                   ru.origen, ru.destino,
                   v.tipo_vehiculo, v.placa
            FROM reservas r
            JOIN horarios h ON r.horario_id = h.id
            JOIN rutas ru ON h.ruta_id = ru.id
            JOIN vehiculos v ON h.vehiculo_id = v.id
            WHERE r.usuario_id = ?
            ORDER BY r.fecha_reserva DESC
        ''', (session['usuario_id'],))
        
        reservas = cursor.fetchall()
        conn.close()
        
        reservas_list = []
        for r in reservas:
            reservas_list.append({
                'id': r[0],
                'codigo_reserva': r[1],
                'nombre_pasajero': r[2],
                'cedula_pasajero': r[3],
                'telefono_pasajero': r[4],
                'precio_total': r[5],
                'estado': r[6],
                'fecha_reserva': r[7],
                'fecha_vencimiento': r[8],
                'notas': r[9],
                'fecha_salida': r[10],
                'fecha_llegada': r[11],
                'origen': r[12],
                'destino': r[13],
                'tipo_vehiculo': r[14],
                'placa': r[15]
            })
        
        return jsonify({
            'success': True,
            'reservas': reservas_list
        })
        
    except Exception as e:
        print(f"Error obteniendo reservas: {e}")
        return jsonify({
            'success': False,
            'message': 'Error obteniendo reservas'
        }), 500

@app.route('/api/mensajes-conversacion/<int:conversacion_id>', methods=['GET'])
def api_mensajes_conversacion(conversacion_id):
    """Obtiene todos los mensajes de una conversación"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Verificar permisos
        cursor.execute('''
            SELECT usuario_id, admin_id
            FROM conversaciones
            WHERE id = ?
        ''', (conversacion_id,))
        
        conv = cursor.fetchone()
        
        if not conv:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Conversación no encontrada'
            }), 404
        
        es_admin = session.get('tipo_usuario') == 'administrador'
        tiene_permiso = (conv[0] == session['usuario_id'] or 
                        conv[1] == session['usuario_id'] or 
                        es_admin)
        
        if not tiene_permiso:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'No tienes permiso para ver esta conversación'
            }), 403
        
        # Obtener mensajes
        cursor.execute('''
            SELECT m.id, m.mensaje, m.fecha_mensaje, m.leido,
                   u.nombre, u.apellido, u.tipo_usuario,
                   m.remitente_id
            FROM mensajes_conversacion m
            JOIN usuarios u ON m.remitente_id = u.id
            WHERE m.conversacion_id = ?
            ORDER BY m.fecha_mensaje ASC
        ''', (conversacion_id,))
        
        mensajes = cursor.fetchall()
        
        # Marcar mensajes como leídos
        cursor.execute('''
            UPDATE mensajes_conversacion
            SET leido = TRUE
            WHERE conversacion_id = ? AND remitente_id != ?
        ''', (conversacion_id, session['usuario_id']))
        
        # Actualizar contador de no leídos
        cursor.execute('''
            UPDATE participantes_conversacion
            SET mensajes_no_leidos = 0, ultima_lectura = CURRENT_TIMESTAMP
            WHERE conversacion_id = ? AND usuario_id = ?
        ''', (conversacion_id, session['usuario_id']))
        
        conn.commit()
        conn.close()
        
        mensajes_list = []
        for m in mensajes:
            mensajes_list.append({
                'id': m[0],
                'mensaje': m[1],
                'fecha_mensaje': m[2],
                'leido': m[3],
                'remitente_nombre': f"{m[4]} {m[5]}",
                'remitente_tipo': m[6],
                'es_mio': m[7] == session['usuario_id']
            })
        
        return jsonify({
            'success': True,
            'mensajes': mensajes_list
        })
        
    except Exception as e:
        print(f"Error obteniendo mensajes: {e}")
        return jsonify({
            'success': False,
            'message': 'Error obteniendo mensajes'
        }), 500


@app.route('/api/notificaciones-chat', methods=['GET'])
def api_notificaciones_chat():
    """Obtiene el número de mensajes no leídos"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COALESCE(SUM(mensajes_no_leidos), 0)
            FROM participantes_conversacion
            WHERE usuario_id = ?
        ''', (session['usuario_id'],))
        
        total_no_leidos = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            'success': True,
            'mensajes_no_leidos': total_no_leidos
        })
        
    except Exception as e:
        print(f"Error obteniendo notificaciones: {e}")
        return jsonify({
            'success': False,
            'message': 'Error obteniendo notificaciones'
        }), 500




# Agregar esta función al archivo auth_server.py y llamarla después de init_db()

def insertar_horarios_prueba():
    """Inserta horarios de prueba para las próximas semanas"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    try:
        # Verificar si ya existen horarios
        cursor.execute('SELECT COUNT(*) FROM horarios')
        if cursor.fetchone()[0] > 0:
            conn.close()
            return  # Ya hay horarios, no insertar más
        
        from datetime import datetime, timedelta
        
        # Obtener IDs de rutas y vehículos
        cursor.execute('SELECT id FROM rutas WHERE activa = 1')
        rutas = [r[0] for r in cursor.fetchall()]
        
        cursor.execute('SELECT id, capacidad_pasajeros FROM vehiculos WHERE activo = 1')
        vehiculos = cursor.fetchall()
        
        if not rutas or not vehiculos:
            print("No hay rutas o vehículos disponibles")
            conn.close()
            return
        
        # Crear horarios para los próximos 30 días
        fecha_inicio = datetime.now()
        horarios_prueba = []
        
        for dia in range(30):
            fecha = fecha_inicio + timedelta(days=dia)
            
            # Para cada ruta
            for ruta_id in rutas:
                # Obtener duración de la ruta
                cursor.execute('SELECT duracion_horas, precio_base FROM rutas WHERE id = ?', (ruta_id,))
                ruta_info = cursor.fetchone()
                duracion_horas = ruta_info[0]
                precio_base = ruta_info[1]
                
                # Crear varios horarios al día
                horas_salida = ['06:00', '09:00', '14:00', '18:00']
                
                for hora_salida in horas_salida:
                    # Seleccionar vehículo aleatorio
                    import random
                    vehiculo = random.choice(vehiculos)
                    vehiculo_id = vehiculo[0]
                    capacidad = vehiculo[1]
                    
                    # Calcular fecha/hora de salida y llegada
                    hora, minuto = map(int, hora_salida.split(':'))
                    fecha_salida = fecha.replace(hour=hora, minute=minuto, second=0, microsecond=0)
                    fecha_llegada = fecha_salida + timedelta(hours=duracion_horas)
                    
                    horarios_prueba.append((
                        ruta_id,
                        vehiculo_id,
                        fecha_salida.strftime('%Y-%m-%d %H:%M:%S'),
                        fecha_llegada.strftime('%Y-%m-%d %H:%M:%S'),
                        precio_base,
                        capacidad,
                        'programado'
                    ))
        
        # Insertar todos los horarios
        cursor.executemany('''
            INSERT INTO horarios (
                ruta_id, vehiculo_id, fecha_salida, fecha_llegada,
                precio, asientos_disponibles, estado
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', horarios_prueba)
        
        conn.commit()
        print(f"✅ Se insertaron {len(horarios_prueba)} horarios de prueba")
        
    except Exception as e:
        print(f"Error insertando horarios de prueba: {e}")
        conn.rollback()
    finally:
        conn.close()
# ============================================
# REEMPLAZAR los endpoints al final de auth_server.py
# (líneas después de api_notificaciones_chat)
# ============================================

@app.route('/api/cerrar-conversacion/<int:conversacion_id>', methods=['POST'])
def cerrar_conversacion(conversacion_id):
    """Cierra una conversación (solo admin)"""
    try:
        if 'usuario_id' not in session:
            return jsonify({'success': False, 'message': 'No autorizado'}), 401
        
        # Verificar que sea admin
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT tipo_usuario FROM usuarios WHERE id = ?", (session['usuario_id'],))
        usuario = cursor.fetchone()
        
        if not usuario or usuario[0] != 'administrador':
            conn.close()
            return jsonify({'success': False, 'message': 'No tienes permisos'}), 403
        
        # Actualizar el estado de la conversación a 'cerrada'
        cursor.execute("""
            UPDATE conversaciones 
            SET estado = 'cerrada',
                fecha_ultima_actividad = CURRENT_TIMESTAMP,
                fecha_cierre = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (conversacion_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Conversación cerrada exitosamente'
        })
        
    except Exception as e:
        print(f"Error cerrando conversación: {e}")
        return jsonify({
            'success': False,
            'message': 'Error al cerrar conversación'
        }), 500


@app.route('/api/cambiar-estado-conversacion/<int:conversacion_id>', methods=['POST'])
def cambiar_estado_conversacion(conversacion_id):
    """Cambia el estado de una conversación"""
    try:
        if 'usuario_id' not in session:
            return jsonify({'success': False, 'message': 'No autorizado'}), 401
        
        data = request.get_json()
        nuevo_estado = data.get('estado')
        
        # Validar que el estado sea válido
        estados_validos = ['abierta', 'en_proceso', 'cerrada']
        if nuevo_estado not in estados_validos:
            return jsonify({
                'success': False,
                'message': 'Estado no válido'
            }), 400
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Verificar permisos de admin
        cursor.execute("SELECT tipo_usuario FROM usuarios WHERE id = ?", (session['usuario_id'],))
        usuario = cursor.fetchone()
        
        if not usuario or usuario[0] != 'administrador':
            conn.close()
            return jsonify({'success': False, 'message': 'No tienes permisos'}), 403
        
        # Actualizar estado
        cursor.execute("""
            UPDATE conversaciones 
            SET estado = ?,
                fecha_ultima_actividad = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (nuevo_estado, conversacion_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Estado actualizado a {nuevo_estado}'
        })
        
    except Exception as e:
        print(f"Error cambiando estado: {e}")
        return jsonify({
            'success': False,
            'message': 'Error al cambiar estado'
        }), 500


@app.route('/api/cambiar-prioridad-conversacion/<int:conversacion_id>', methods=['POST'])
def cambiar_prioridad_conversacion(conversacion_id):
    """Cambia la prioridad de una conversación"""
    try:
        if 'usuario_id' not in session:
            return jsonify({'success': False, 'message': 'No autorizado'}), 401
        
        data = request.get_json()
        nueva_prioridad = data.get('prioridad')
        
        # Validar que la prioridad sea válida
        prioridades_validas = ['baja', 'media', 'alta', 'urgente']
        if nueva_prioridad not in prioridades_validas:
            return jsonify({
                'success': False,
                'message': 'Prioridad no válida'
            }), 400
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Verificar permisos de admin
        cursor.execute("SELECT tipo_usuario FROM usuarios WHERE id = ?", (session['usuario_id'],))
        usuario = cursor.fetchone()
        
        if not usuario or usuario[0] != 'administrador':
            conn.close()
            return jsonify({'success': False, 'message': 'No tienes permisos'}), 403
        
        # Actualizar prioridad
        cursor.execute("""
            UPDATE conversaciones 
            SET prioridad = ?,
                fecha_ultima_actividad = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (nueva_prioridad, conversacion_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Prioridad actualizada a {nueva_prioridad}'
        })
        
    except Exception as e:
        print(f"Error cambiando prioridad: {e}")
        return jsonify({
            'success': False,
            'message': 'Error al cambiar prioridad'
        }), 500


@app.route('/api/reabrir-conversacion/<int:conversacion_id>', methods=['POST'])
def reabrir_conversacion(conversacion_id):
    """Reabre una conversación cerrada"""
    try:
        if 'usuario_id' not in session:
            return jsonify({'success': False, 'message': 'No autorizado'}), 401
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Verificar permisos de admin
        cursor.execute("SELECT tipo_usuario FROM usuarios WHERE id = ?", (session['usuario_id'],))
        usuario = cursor.fetchone()
        
        if not usuario or usuario[0] != 'administrador':
            conn.close()
            return jsonify({'success': False, 'message': 'No tienes permisos'}), 403
        
        # Reabrir conversación
        cursor.execute("""
            UPDATE conversaciones 
            SET estado = 'abierta',
                fecha_ultima_actividad = CURRENT_TIMESTAMP,
                fecha_cierre = NULL
            WHERE id = ?
        """, (conversacion_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Conversación reabierta'
        })
        
    except Exception as e:
        print(f"Error reabriendo conversación: {e}")
        return jsonify({
            'success': False,
            'message': 'Error al reabrir conversación'
        }), 500


@app.route('/api/asignar-conversacion/<int:conversacion_id>', methods=['POST'])
def asignar_conversacion(conversacion_id):
    """Asigna una conversación a un administrador específico"""
    try:
        if 'usuario_id' not in session:
            return jsonify({'success': False, 'message': 'No autorizado'}), 401
        
        data = request.get_json()
        admin_asignado_id = data.get('admin_id')
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Verificar que el admin asignado existe
        cursor.execute("""
            SELECT id, nombre, apellido 
            FROM usuarios 
            WHERE id = ? AND tipo_usuario = 'administrador'
        """, (admin_asignado_id,))
        
        admin_asignado = cursor.fetchone()
        
        if not admin_asignado:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Administrador no encontrado'
            }), 404
        
        # Asignar conversación
        cursor.execute("""
            UPDATE conversaciones 
            SET admin_id = ?,
                fecha_ultima_actividad = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (admin_asignado_id, conversacion_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Conversación asignada a {admin_asignado[1]} {admin_asignado[2]}'
        })
        
    except Exception as e:
        print(f"Error asignando conversación: {e}")
        return jsonify({
            'success': False,
            'message': 'Error al asignar conversación'
        }), 500


# ============================================
# ENDPOINT DE DEBUG PARA VER CONVERSACIONES
# ============================================
@app.route('/api/debug/conversaciones', methods=['GET'])
def debug_conversaciones():
    """Endpoint de debug para ver todas las conversaciones"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Ver todas las conversaciones
        cursor.execute("""
            SELECT c.id, c.asunto, c.tipo, c.estado, c.prioridad,
                   c.usuario_id, u.nombre, u.apellido,
                   c.admin_id, a.nombre, a.apellido,
                   c.fecha_creacion, c.fecha_ultima_actividad
            FROM conversaciones c
            JOIN usuarios u ON c.usuario_id = u.id
            LEFT JOIN usuarios a ON c.admin_id = a.id
            ORDER BY c.fecha_ultima_actividad DESC
        """)
        
        conversaciones = cursor.fetchall()
        
        # Contar mensajes por conversación
        cursor.execute("""
            SELECT conversacion_id, COUNT(*) as total
            FROM mensajes_conversacion
            GROUP BY conversacion_id
        """)
        
        mensajes_count = {row[0]: row[1] for row in cursor.fetchall()}
        
        conn.close()
        
        result = []
        for c in conversaciones:
            result.append({
                'id': c[0],
                'asunto': c[1],
                'tipo': c[2],
                'estado': c[3],
                'prioridad': c[4],
                'usuario': f"{c[6]} {c[7]} (ID: {c[5]})",
                'admin': f"{c[9]} {c[10]}" if c[8] else 'Sin asignar',
                'total_mensajes': mensajes_count.get(c[0], 0),
                'fecha_creacion': c[11],
                'fecha_ultima_actividad': c[12]
            })
        
        return jsonify({
            'success': True,
            'total_conversaciones': len(conversaciones),
            'conversaciones': result
        })
        
    except Exception as e:
        print(f"Error en debug: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

if __name__ == '__main__':
    init_db() 
    actualizar_db_conversaciones() 
    insertar_horarios_prueba()
    crear_primer_admin() 
    
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    app.run(debug=True, host='0.0.0.0', port=5000)