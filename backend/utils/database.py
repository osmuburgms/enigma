import json
from enum import Enum

class AttributeType(Enum):
    """Tipos de atributos en el Enigma de Einstein"""
    COLOR = "color"
    NATIONALITY = "nacionalidad"
    PET = "mascota"
    FOOD = "comida"
    DULCES = "dulces"

class Database:
    """Base de datos para el Enigma del Einstein"""
    
    def __init__(self):
        # Mapeo UID -> (tipo_atributo, valor)
        # Ejemplo: "AB CD EF 01" -> (AttributeType.COLOR, "Rojo")
        self.rfid_tags = {}
        
        # Estado del tablero: {(fila, columna): uid}
        # fila: 1-5 (sensor), columna: 1-5 (ESP)
        self.board_state = {}
        
        # Historial de movimientos
        self.moves_history = []
        
        # Atributos registrados (para validar) - valores únicos por tipo
        self.registered_attributes = {attr_type: set() for attr_type in AttributeType}
        
        self._initialize_board()
    
    def _initialize_board(self):
        """Inicializa el tablero vacío (5x5)"""
        for row in range(1, 6):
            for col in range(1, 6):
                self.board_state[(row, col)] = None
    
    def register_rfid(self, uid, attribute_type, attribute_value):
        """Registra una tarjeta RFID con su atributo
        
        Args:
            uid: UID de la tarjeta (ej: "AB CD EF 01")
            attribute_type: AttributeType enum
            attribute_value: valor del atributo (ej: "Rojo")
            
        Returns:
            bool: True si se registró, False si ya existe
        """
        if uid in self.rfid_tags:
            print(f"[DB] Tarjeta {uid} ya registrada")
            return False
        
        self.rfid_tags[uid] = {
            "type": attribute_type.value,
            "value": attribute_value
        }
        self.registered_attributes[attribute_type].add(attribute_value)
        print(f"[DB] Tarjeta registrada: {uid} -> {attribute_type.value}: {attribute_value}")
        return True
    
    def place_tag(self, uid, row, col):
        """Coloca una tarjeta RFID en una posición del tablero
        
        Si el tag ya está en otra posición, lo mueve automáticamente.
        
        Args:
            uid: UID de la tarjeta
            row: fila (1-5, sensor)
            col: columna (1-5, ESP)
            
        Returns:
            dict: {"success": bool, "message": str, "violations": list, "moved_from": tuple or None}
        """
        # Validar posición
        if not self._validate_position(row, col):
            return {
                "success": False,
                "message": f"Posición inválida: ({row}, {col})",
                "violations": [],
                "moved_from": None
            }
        
        # Validar UID
        if uid not in self.rfid_tags:
            return {
                "success": False,
                "message": f"UID {uid} no registrado",
                "violations": [],
                "moved_from": None
            }
        
        # Verificar si el tag ya está en otra posición
        moved_from = None
        for (r, c), tag in self.board_state.items():
            if tag == uid and (r, c) != (row, col):
                # El tag está en otra posición - lo movemos
                moved_from = (r, c)
                self.board_state[(r, c)] = None
                print(f"[DB] Tag {uid} movido desde ({r}, {c}) a ({row}, {col})")
                break
        
        # Verificar violaciones (excluyendo la regla de tag duplicado)
        violations = self._check_violations(uid, row, col, exclude_tag_duplicate=True)
        
        if violations:
            # Si hay violaciones, restaurar la posición anterior si se movió
            if moved_from:
                self.board_state[moved_from] = uid
                print(f"[DB] Movimiento revertido por violaciones: {uid} restaurado en {moved_from}")
            
            return {
                "success": False,
                "message": "Movimiento inválido: violaciones detectadas",
                "violations": violations,
                "moved_from": moved_from
            }
        
        # Remover tag anterior si existe en la celda destino
        old_tag = self.board_state[(row, col)]
        if old_tag and old_tag != uid:
            print(f"[DB] Removiendo tag anterior de destino: {old_tag}")
        
        # Colocar el nuevo tag
        self.board_state[(row, col)] = uid
        
        # Registrar movimiento
        move = {
            "uid": uid,
            "position": (row, col),
            "attribute": self.rfid_tags[uid],
            "moved_from": moved_from
        }
        self.moves_history.append(move)
        
        action = "movido" if moved_from else "colocado"
        print(f"[DB] Tag {action}: {uid} en posición ({row}, {col})")
        return {
            "success": True,
            "message": f"Tag {action} en ({row}, {col})",
            "violations": [],
            "moved_from": moved_from
        }
    
    def _validate_position(self, row, col):
        """Valida que la posición esté dentro del tablero"""
        return 1 <= row <= 5 and 1 <= col <= 5
    
    def _check_violations(self, uid, row, col, exclude_tag_duplicate=False):
        """Verifica si colocar un tag viola las reglas
        
        Args:
            uid: UID del tag a verificar
            row, col: Posición donde se quiere colocar
            exclude_tag_duplicate: Si True, no verifica duplicado de tags
            
        Returns:
            list: Lista de violaciones encontradas
        """
        violations = []
        attribute = self.rfid_tags[uid]
        attr_type = attribute["type"]
        attr_value = attribute["value"]
        
        # Verificar si el tag ya está en el tablero (en otra celda)
        # Solo si no se excluye esta verificación
        if not exclude_tag_duplicate:
            for (r, c), tag in self.board_state.items():
                if tag == uid and (r, c) != (row, col):
                    violations.append(f"Tag {uid} ya está en posición ({r}, {c})")
                    return violations
        
        # Verificar valores duplicados en la misma fila (tipo ya es el mismo)
        # Solo si el tag no está ya en la fila (para permitir movimientos)
        tag_already_in_row = any(
            self.board_state.get((row, c)) == uid for c in range(1, 6)
        )
        if not tag_already_in_row:
            for c in range(1, 6):
                if (row, c) in self.board_state and self.board_state[(row, c)]:
                    existing_tag = self.board_state[(row, c)]
                    # No verificar contra sí mismo si es el mismo tag moviéndose
                    if existing_tag != uid:
                        existing_attr = self.rfid_tags[existing_tag]
                        if existing_attr["value"] == attr_value:
                            violations.append(
                                f"Ya existe {attr_value} en fila {row}: (en columna {c})"
                            )
        
        # Verificar tipos duplicados en la misma columna
        for r in range(1, 6):
            if r != row and (r, col) in self.board_state and self.board_state[(r, col)]:
                existing_tag = self.board_state[(r, col)]
                # No verificar contra sí mismo si es el mismo tag moviéndose
                if existing_tag != uid:
                    existing_attr = self.rfid_tags[existing_tag]
                    if existing_attr["type"] == attr_type:
                        violations.append(
                            f"Ya existe {attr_type} en columna {col}: (en fila {r})"
                        )
        
        return violations
    
    def remove_tag(self, row, col):
        """Remueve una tarjeta del tablero"""
        if not self._validate_position(row, col):
            return False
        
        if self.board_state[(row, col)] is None:
            return False
        
        self.board_state[(row, col)] = None
        print(f"[DB] Tag removido de posición ({row}, {col})")
        return True
    
    def get_board_state(self):
        """Retorna el estado actual del tablero con detalles de tags"""
        board_info = {}
        for (row, col), tag in self.board_state.items():
            if tag:
                board_info[(row, col)] = {
                    "uid": tag,
                    "attribute": self.rfid_tags[tag]
                }
            else:
                board_info[(row, col)] = None
        return board_info
    
    def get_position(self, uid):
        """Obtiene la posición actual de un tag
        
        Returns:
            tuple: (row, col) o None si no existe
        """
        for (row, col), tag in self.board_state.items():
            if tag == uid:
                return (row, col)
        return None
    
    def is_complete(self):
        """Verifica si el tablero está completamente lleno"""
        return all(tag is not None for tag in self.board_state.values())
    
    def get_statistics(self):
        """Retorna estadísticas del tablero"""
        filled = sum(1 for tag in self.board_state.values() if tag is not None)
        return {
            "total_cells": 25,
            "filled_cells": filled,
            "empty_cells": 25 - filled,
            "registered_tags": len(self.rfid_tags),
            "moves_count": len(self.moves_history),
            "completion_percentage": (filled / 25) * 100
        }
    
    def export_state(self):
        """Exporta el estado actual del tablero como JSON"""
        export_data = {
            "board": self.get_board_state(),
            "statistics": self.get_statistics(),
            "registered_tags": self.rfid_tags
        }
        return json.dumps(export_data, indent=2, ensure_ascii=False)
    
    def reset_board(self):
        """Limpia el tablero (mantiene los tags registrados)"""
        self._initialize_board()
        self.moves_history = []
        print("[DB] Tablero reiniciado")
