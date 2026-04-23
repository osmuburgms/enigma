import json
import os
import random
from utils.database import Database, AttributeType

class Clue:
    """Representa una pista del puzzle"""
    def __init__(self, clue_id, description, rule):
        self.clue_id = clue_id
        self.description = description
        self.rule = rule  # función que valida la regla
    
    def validate(self, board_state):
        """Valida si la pista se cumple en el estado actual"""
        try:
            return self.rule(board_state)
        except Exception as e:
            print(f"[CLUE] Error validando pista {self.clue_id}: {e}")
            return False

class GameLogic:
    """Lógica principal del Enigma del Einstein"""
    
    # Mapeo de filas a tipos de atributos
    ROW_TYPES = {
        1: AttributeType.COLOR,
        2: AttributeType.NATIONALITY,
        3: AttributeType.PET,
        4: AttributeType.FOOD,
        5: AttributeType.DULCES
    }
    
    SPECIAL_UID = "24 B1 46 BC"

    def __init__(self, mqtt, frontend_callback=None):
        self.mqtt = mqtt
        self.frontend_callback = frontend_callback
        self.db = Database()
        self.game_state = "initialized"  # initialized, running, completed, paused, stopped
        self.clues = []
        self.last_tag = {
            "uid": "--",
            "esp": None,
            "sensor": None,
            "attribute": "--",
            "value": "--"
        }
        self._initialize_game()

    def _emit_frontend_event(self, event_name, payload):
        if callable(self.frontend_callback):
            try:
                self.frontend_callback(event_name, payload)
            except Exception as e:
                print(f"[LOGIC] Error enviando evento frontend {event_name}: {e}")

    def _log(self, message):
        payload = {"message": message}
        self._emit_frontend_event("backend_log", payload)
        print(message)

    def _initialize_game(self):
        """Inicializa el juego con tarjetas RFID de ejemplo"""
        self._log("[LOGIC] Inicializando juego...")
        
        # Registrar tarjetas RFID con sus atributos
        # COLORES (5 tarjetas)
        self.db.register_rfid("AB CD EF 01", AttributeType.COLOR, "Rojo")
        self.db.register_rfid("AB CD EF 02", AttributeType.COLOR, "Azul")
        self.db.register_rfid("AB CD EF 03", AttributeType.COLOR, "Verde")
        self.db.register_rfid("AB CD EF 04", AttributeType.COLOR, "Amarillo")
        self.db.register_rfid("AB CD EF 05", AttributeType.COLOR, "Blanco")
        
        # NACIONALIDADES (5 tarjetas)
        self.db.register_rfid("0A AB 58 BF", AttributeType.NATIONALITY, "Inglés")
        self.db.register_rfid("43 FF DC 06", AttributeType.NATIONALITY, "Sueco")
        self.db.register_rfid("E9 A1 11 4D", AttributeType.NATIONALITY, "Danés")
        self.db.register_rfid("50 2B D0 A6", AttributeType.NATIONALITY, "Noruego")
        self.db.register_rfid("A0 77 93 5E", AttributeType.NATIONALITY, "Alemán")
        
        # MASCOTAS (5 tarjetas)
        self.db.register_rfid("22 33 44 55", AttributeType.PET, "Perro")
        self.db.register_rfid("22 33 44 56", AttributeType.PET, "Gato")
        self.db.register_rfid("22 33 44 57", AttributeType.PET, "Pájaro")
        self.db.register_rfid("22 33 44 58", AttributeType.PET, "Pez")
        self.db.register_rfid("22 33 44 59", AttributeType.PET, "Caballo")
        
        # COMIDAS (5 tarjetas)
        self.db.register_rfid("33 44 55 66", AttributeType.FOOD, "Té")
        self.db.register_rfid("33 44 55 67", AttributeType.FOOD, "Café")
        self.db.register_rfid("33 44 55 68", AttributeType.FOOD, "Leche")
        self.db.register_rfid("33 44 55 69", AttributeType.FOOD, "Cerveza")
        self.db.register_rfid("33 44 55 70", AttributeType.FOOD, "Agua")
        
        # DULCES (5 tarjetas)
        self.db.register_rfid("44 55 66 77", AttributeType.DULCES, "chocolate")
        self.db.register_rfid("44 55 66 78", AttributeType.DULCES, "galletas")
        self.db.register_rfid("44 55 66 79", AttributeType.DULCES, "paleta")
        self.db.register_rfid("44 55 66 80", AttributeType.DULCES, "caramelos")
        self.db.register_rfid("44 55 66 81", AttributeType.DULCES, "malvaviscos")
        
        self._prepare_new_puzzle()
        self.game_state = "running"
        self._log("[LOGIC] Juego inicializado correctamente")
        self._print_board()  # Mostrar tablero inicial vacío
        self._broadcast_board_state()
    
    SCENARIO_FILE = os.path.join(os.path.dirname(__file__), "scenarios.json")

    def _prepare_new_puzzle(self):
        """Selecciona un escenario predefinido y prepara la solución y las pistas."""
        scenarios = self._load_scenarios()
        if not scenarios:
            self._log("[LOGIC] No se encontraron escenarios válidos, usando solución aleatoria.")
            self.solution = self._generate_random_solution()
            self._initialize_clues()
            return

        self.current_scenario = random.choice(scenarios)
        self.solution = self.current_scenario["solution"]
        self._initialize_clues_from_scenario(self.current_scenario)
        self.mqtt.publish(
            "guardian/system/log",
            f"Escenario seleccionado: {self.current_scenario.get('name', 'sin nombre')} (pez en casa ESP{self.current_scenario.get('fish_house')})"
        )
    
    def _load_scenarios(self):
        try:
            with open(self.SCENARIO_FILE, encoding="utf-8") as f:
                data = json.load(f)
            scenarios = data.get("scenarios", [])
            return [s for s in scenarios if "solution" in s and "clues" in s]
        except Exception as e:
            self._log(f"[LOGIC] Error cargando escenarios: {e}")
            return []

    def _build_rule(self, rule_data):
        rule_type = rule_data.get("type")
        if rule_type == "same_column":
            return self._same_column_rule(
                rule_data["attr"],
                rule_data["value"],
                rule_data["other_attr"],
                rule_data["other_value"]
            )
        if rule_type == "adjacent":
            return self._adjacent_rule(
                rule_data["attr"],
                rule_data["value"],
                rule_data["adjacent_attr"],
                rule_data["adjacent_value"]
            )
        if rule_type == "center":
            return self._center_house_rule(rule_data["attr"], rule_data["value"])
        if rule_type == "first":
            return self._first_house_rule(rule_data["attr"], rule_data["value"])
        if rule_type == "left_right":
            return self._left_right_rule(rule_data["left_value"], rule_data["right_value"])
        return lambda board: None

    def _initialize_clues_from_scenario(self, scenario):
        self.clues = []
        for clue_data in scenario["clues"]:
            rule = self._build_rule(clue_data.get("rule", {}))
            self.clues.append(Clue(clue_data["id"], clue_data["description"], rule))

    def _same_column_rule(self, attr_type, expected_value, other_attr_type, other_expected_value):
        def rule(board):
            mismatch_found = False
            row_a = self._row_for_type(attr_type)
            row_b = self._row_for_type(other_attr_type)
            for col in range(1, 6):
                a = board.get((row_a, col))
                b = board.get((row_b, col))
                if a and b:
                    if a["attribute"]["value"] == expected_value and b["attribute"]["value"] == other_expected_value:
                        return True
                    mismatch_found = True
            return False if mismatch_found else None
        return rule

    def _adjacent_rule(self, attr_type, attr_value, adjacent_attr_type, adjacent_attr_value):
        def rule(board):
            row_a = self._row_for_type(attr_type)
            row_b = self._row_for_type(adjacent_attr_type)
            item_found = False
            for col in range(1, 6):
                item = board.get((row_a, col))
                if item and item["attribute"]["value"] == attr_value:
                    item_found = True
                    for adj in [col - 1, col + 1]:
                        if 1 <= adj <= 5:
                            neighbor = board.get((row_b, adj))
                            if neighbor:
                                if neighbor["attribute"]["value"] == adjacent_attr_value:
                                    return True
                                return False
            return None if not item_found else None
        return rule

    def _center_house_rule(self, attr_type, attr_value):
        def rule(board):
            center = board.get((self._row_for_type(attr_type), 3))
            if not center:
                return None
            return center["attribute"]["value"] == attr_value
        return rule

    def _first_house_rule(self, attr_type, attr_value):
        def rule(board):
            first = board.get((self._row_for_type(attr_type), 1))
            if not first:
                return None
            return first["attribute"]["value"] == attr_value
        return rule

    def _left_right_rule(self, left_value, right_value):
        def rule(board):
            info_found = False
            for col in range(1, 5):
                left = board.get((1, col))
                right = board.get((1, col + 1))
                if left and right:
                    info_found = True
                    if left["attribute"]["value"] == left_value and right["attribute"]["value"] == right_value:
                        return True
            return False if info_found else None
        return rule

    def _generate_random_solution(self):
        """Genera una asignación aleatoria de atributos por casa."""
        colors = ["Rojo", "Azul", "Verde", "Amarillo", "Blanco"]
        nationalities = ["Inglés", "Sueco", "Danés", "Noruego", "Alemán"]
        pets = ["Perro", "Gato", "Pájaro", "Pez", "Caballo"]
        foods = ["Té", "Café", "Leche", "Cerveza", "Agua"]
        candies = ["chocolate", "galletas", "paleta", "caramelos", "malvaviscos"]
        random.shuffle(colors)
        random.shuffle(nationalities)
        random.shuffle(pets)
        random.shuffle(foods)
        random.shuffle(candies)
        return {
            col: {
                "color": colors[col-1],
                "nacionalidad": nationalities[col-1],
                "mascota": pets[col-1],
                "comida": foods[col-1],
                "dulces": candies[col-1]
            }
            for col in range(1, 6)
        }
    
    def _get_column_for_value(self, attr_type, value):
        for col, data in self.solution.items():
            if data.get(attr_type) == value:
                return col
        return None

    def _row_for_type(self, attr_type):
        for row, type_enum in self.ROW_TYPES.items():
            if type_enum.value == attr_type:
                return row
        raise ValueError(f"Tipo de atributo desconocido: {attr_type}")

    def _initialize_clues(self):
        """Define las pistas del puzzle del Enigma de Einstein según la solución actual."""
        
        # Descripciones dinámicas basadas en la solución generada
        color_for_english = self.solution[self._get_column_for_value("nacionalidad", "Inglés")]["color"]
        pet_for_sueco = self.solution[self._get_column_for_value("nacionalidad", "Sueco")]["mascota"]
        drink_for_danes = self.solution[self._get_column_for_value("nacionalidad", "Danés")]["comida"]
        green_col = self._get_column_for_value("color", "Verde")
        white_col = self._get_column_for_value("color", "Blanco")
        coffee_col = self._get_column_for_value("comida", "Café")
        pallmall_col = self._get_column_for_value("dulces", "chocolate")
        yellow_col = self._get_column_for_value("color", "Amarillo")
        center_drink = self.solution[3]["comida"]
        first_nationality = self.solution[1]["nacionalidad"]
        blue_col = self._get_column_for_value("color", "Azul")
        norwegian_col = self._get_column_for_value("nacionalidad", "Noruego")
        german_col = self._get_column_for_value("nacionalidad", "Alemán")
        rothmans_col = self._get_column_for_value("dulces", "malvaviscos")
        water_col = self._get_column_for_value("comida", "Agua")
        
        # Buscar un par válido para la pista de la casa verde-a-la-izquierda-de-blanca
        left_color = None
        right_color = None
        for col in range(1, 5):
            if self.solution[col]["color"] == "Verde" and self.solution[col + 1]["color"] == "Blanco":
                left_color = "Verde"
                right_color = "Blanco"
                break
        if left_color is None:
            for col in range(1, 5):
                if self.solution[col]["color"] != self.solution[col + 1]["color"]:
                    left_color = self.solution[col]["color"]
                    right_color = self.solution[col + 1]["color"]
                    break
        
        # Buscar un dulce que tenga al lado al gato
        sweet_next_to_cat = None
        for col in range(1, 6):
            pet = self.solution[col]["mascota"]
            if pet == "Gato":
                for adj in [col - 1, col + 1]:
                    if 1 <= adj <= 5:
                        sweet_next_to_cat = self.solution[adj]["dulces"]
                        break
                if sweet_next_to_cat:
                    break
        
        # Buscar una mascota al lado de galletas
        pet_next_to_dunhill = None
        dunhill_col = self._get_column_for_value("dulces", "galletas")
        for adj in [dunhill_col - 1, dunhill_col + 1]:
            if 1 <= adj <= 5:
                pet_next_to_dunhill = self.solution[adj]["mascota"]
                break
        
        # Buscar un dulce que esté al lado del agua
        sweet_next_to_water = None
        for col in range(1, 6):
            if self.solution[col]["comida"] == "Agua":
                for adj in [col - 1, col + 1]:
                    if 1 <= adj <= 5:
                        sweet_next_to_water = self.solution[adj]["dulces"]
                        break
                if sweet_next_to_water:
                    break
        
        color_at_coffee = self.solution[coffee_col]["color"]
        pet_at_pallmall = self.solution[pallmall_col]["mascota"]
        sweet_at_yellow = self.solution[yellow_col]["dulces"]
        nationality_at_blue_neighbor = None
        for adj in [blue_col - 1, blue_col + 1]:
            if 1 <= adj <= 5:
                nationality_at_blue_neighbor = self.solution[adj]["nacionalidad"]
                break
        
        def same_column_rule(attr_type, expected_value, other_attr_type, other_expected_value):
            def rule(board):
                mismatch_found = False
                row_a = self._row_for_type(attr_type)
                row_b = self._row_for_type(other_attr_type)
                for col in range(1, 6):
                    a = board.get((row_a, col))
                    b = board.get((row_b, col))
                    if a and b:
                        if a["attribute"]["value"] == expected_value and b["attribute"]["value"] == other_expected_value:
                            return True
                        mismatch_found = True
                return False if mismatch_found else None
            return rule

        def adjacent_rule(attr_type, attr_value, adjacent_attr_type, adjacent_attr_value):
            def rule(board):
                row_a = self._row_for_type(attr_type)
                row_b = self._row_for_type(adjacent_attr_type)
                item_found = False
                for col in range(1, 6):
                    item = board.get((row_a, col))
                    if item and item["attribute"]["value"] == attr_value:
                        item_found = True
                        for adj in [col - 1, col + 1]:
                            if 1 <= adj <= 5:
                                neighbor = board.get((row_b, adj))
                                if neighbor:
                                    if neighbor["attribute"]["value"] == adjacent_attr_value:
                                        return True
                                    return False
                return None if not item_found else None
            return rule

        def center_house_rule(attr_type, attr_value):
            def rule(board):
                center = board.get((self._row_for_type(attr_type), 3))
                if not center:
                    return None
                return center["attribute"]["value"] == attr_value
            return rule

        def first_house_rule(attr_type, attr_value):
            def rule(board):
                first = board.get((self._row_for_type(attr_type), 1))
                if not first:
                    return None
                return first["attribute"]["value"] == attr_value
            return rule

        def left_right_rule(left_value, right_value):
            def rule(board):
                info_found = False
                for col in range(1, 5):
                    left = board.get((1, col))
                    right = board.get((1, col + 1))
                    if left and right:
                        info_found = True
                        if left["attribute"]["value"] == left_value and right["attribute"]["value"] == right_value:
                            return True
                return False if info_found else None
            return rule
        
        self.clues = [
            Clue(1, f"El inglés vive en la casa {color_for_english.lower()}", same_column_rule("nacionalidad", "Inglés", "color", color_for_english)),
            Clue(2, f"El sueco tiene un {pet_for_sueco.lower()} como mascota", same_column_rule("nacionalidad", "Sueco", "mascota", pet_for_sueco)),
            Clue(3, f"El danés toma {drink_for_danes.lower()}", same_column_rule("nacionalidad", "Danés", "comida", drink_for_danes)),
            Clue(4, f"La casa {left_color.lower()} está inmediatamente a la izquierda de la casa {right_color.lower()}", left_right_rule(left_color, right_color)),
            Clue(5, f"El dueño de la casa {color_at_coffee.lower()} bebe café", same_column_rule("color", color_at_coffee, "comida", "Café")),
            Clue(6, f"La persona que come chocolate cría {pet_at_pallmall.lower()}", same_column_rule("dulces", "chocolate", "mascota", pet_at_pallmall)),
            Clue(7, f"El dueño de la casa {self.solution[yellow_col]['color'].lower()} come {sweet_at_yellow}", same_column_rule("color", self.solution[yellow_col]["color"], "dulces", sweet_at_yellow)),
            Clue(8, f"El hombre que vive en la casa del centro bebe {center_drink.lower()}", center_house_rule("comida", center_drink)),
            Clue(9, f"El {first_nationality.lower()} vive en la primera casa", first_house_rule("nacionalidad", first_nationality)),
            Clue(10, f"El hombre que come {sweet_next_to_cat} vive al lado del que tiene un gato", adjacent_rule("dulces", sweet_next_to_cat, "mascota", "Gato")),
            Clue(11, f"El hombre que tiene un {pet_next_to_dunhill.lower()} vive al lado del que come galletas", adjacent_rule("mascota", pet_next_to_dunhill, "dulces", "galletas")),
            Clue(12, f"El hombre que come chocolate bebe cerveza", same_column_rule("dulces", "chocolate", "comida", "Cerveza")),
            Clue(13, f"El {nationality_at_blue_neighbor.lower()} vive al lado de la casa azul", adjacent_rule("nacionalidad", nationality_at_blue_neighbor, "color", "Azul")),
            Clue(14, f"El {self.solution[german_col]['nacionalidad'].lower()} come {self.solution[german_col]['dulces']}", same_column_rule("nacionalidad", self.solution[german_col]["nacionalidad"], "dulces", self.solution[german_col]["dulces"])),
            Clue(15, f"El hombre que come {sweet_next_to_water} vive al lado del que bebe agua", adjacent_rule("dulces", sweet_next_to_water, "comida", "Agua")),
        ]
    
    def process_rfid(self, uid, esp_id, sensor_id):
        """Procesa un tag RFID detectado
        
        Si el tag ya está en otra posición, lo mueve automáticamente.
        
        Args:
            uid: UID del tag
            esp_id: ID de la ESP que detector (1-5, columna)
            sensor_id: ID del sensor en la ESP (1-5, fila)
            
        Returns:
            dict: resultado del procesamiento
        """
        self._log(f"[LOGIC] Procesando RFID - UID: {uid}, ESP: {esp_id}, Sensor: {sensor_id}")

        tag_info = self.db.rfid_tags.get(uid)
        self.last_tag = {
            "uid": uid,
            "esp": esp_id,
            "sensor": sensor_id,
            "attribute": tag_info["type"] if tag_info else "--",
            "value": tag_info["value"] if tag_info else "--"
        }
        
        # Validar IDs
        if not (1 <= esp_id <= 5 and 1 <= sensor_id <= 5):
            msg = f"IDs inválidos: ESP={esp_id}, Sensor={sensor_id}"
            self._log(f"[LOGIC] {msg}")
            self.mqtt.publish("guardian/system/log", msg)
            return {"success": False, "message": msg}
        
        # Check special UID commands
        if uid == self.SPECIAL_UID:
            board_has_pieces = any(tag is not None for tag in self.db.board_state.values())
            if board_has_pieces:
                self._log("[LOGIC] UID especial detectado: reiniciando juego")
                self.mqtt.publish("guardian/system/log", "UID especial detectado: reiniciando juego")
                self.reset_game()
                return {"success": True, "message": "Juego reiniciado por UID especial"}
            else:
                self._log("[LOGIC] UID especial detectado: apagando juego")
                self.game_state = "stopped"
                self._broadcast_board_state()
                self.mqtt.publish("guardian/system/log", "Juego apagado por UID especial")
                return {"success": True, "message": "Juego apagado por UID especial"}

        # Verificar que el tag esté registrado
        tag_info = self.db.rfid_tags.get(uid)
        if not tag_info:
            msg = f"UID {uid} no registrado"
            self._log(f"[LOGIC] {msg}")
            self.mqtt.publish("guardian/system/log", msg)
            return {"success": False, "message": msg}
        
        # Verificar que el tipo de atributo coincida con la fila
        expected_type = self.ROW_TYPES[sensor_id]
        if tag_info["type"] != expected_type.value:
            msg = f"Tipo de atributo incorrecto para fila {sensor_id}: esperado {expected_type.value}, obtenido {tag_info['type']}"
            self._log(f"[LOGIC] {msg}")
            self.mqtt.publish("guardian/system/log", msg)
            return {"success": False, "message": msg}
        
        # Intentar colocar/mover el tag
        result = self.db.place_tag(uid, row=sensor_id, col=esp_id)
        
        if result["success"]:
            # Tag colocado/movido exitosamente
            moved_from = result.get("moved_from")
            action = "movido" if moved_from else "colocado"
            
            # Log detallado
            if moved_from:
                self._log(f"[LOGIC] Tag {action}: {uid} de {moved_from} a ({sensor_id}, {esp_id})")
                self.mqtt.publish("guardian/system/log", 
                    f"Tag movido: {uid} de {moved_from} a ({sensor_id}, {esp_id})")
            else:
                self._log(f"[LOGIC] Tag {action}: {uid} en ({sensor_id}, {esp_id})")
                self.mqtt.publish("guardian/system/log", 
                    f"Tag colocado: {uid} en ({sensor_id}, {esp_id})")
            
            # Actualizar estado del tablero
            self._broadcast_board_state()
            self._print_board()  # Mostrar tablero en terminal
            self._check_win_condition()
            return result
        else:
            # Error al colocar/mover
            self._log(f"[LOGIC] Error: {result['message']}")
            if result["violations"]:
                msg = " | ".join(result["violations"])
                self._log(f"[LOGIC] Violaciones: {msg}")
            else:
                msg = result["message"]
            self.mqtt.publish("guardian/system/log", f"ERROR: {msg}")
            return result
    
    def _print_board(self):
        """Imprime una representación gráfica del tablero en la terminal"""
        board_state = self.db.get_board_state()
        
        print("\n" + "="*60)
        print("           TABLERO DEL ENIGMA DEL EINSTEIN")
        print("="*60)
        
        # Encabezado de columnas (ESP IDs)
        print("     ", end="")
        for col in range(1, 6):
            print(f" ESP{col} ", end="")
        print()
        
        # Línea separadora
        print("     ┌" + "─────┬" * 4 + "─────┐")
        
        for row in range(1, 6):
            # Fila de sensores
            print(f" S{row} │", end="")
            
            for col in range(1, 6):
                cell_data = board_state.get((row, col))
                if cell_data:
                    # Hay una ficha - mostrar atributo abreviado
                    attr = cell_data["attribute"]
                    attr_type = attr["type"]
                    attr_value = attr["value"]
                    
                    # Abreviaturas para mantener el formato
                    if attr_type == "color":
                        abbr = attr_value[:3].upper()  # ROJ, AZU, VER, AMA, BLA
                    elif attr_type == "nacionalidad":
                        abbr = attr_value[:3].upper()  # ING, SUE, DAN, NOR, ALE
                    elif attr_type == "mascota":
                        abbr = attr_value[:3].upper()  # PER, GAT, PAJ, PEZ, CAB
                    elif attr_type == "comida":
                        abbr = attr_value[:3].upper()  # TE, CAF, LEC, CER, AGU
                    elif attr_type == "dulces":
                        abbr = attr_value[:3].upper()
                    else:
                        abbr = "???"
                    
                    print(f" {abbr} │", end="")
                else:
                    # Celda vacía
                    print("     │", end="")
            
            print()
            
            # Línea separadora (excepto después de la última fila)
            if row < 5:
                print("     ├" + "─────┼" * 4 + "─────┤")
        
        # Línea inferior
        print("     └" + "─────┴" * 4 + "─────┘")
        
        # Leyenda
        print("\nLEYENDA:")
        print("ROJ=Rojo, AZU=Azul, VER=Verde, AMA=Amarillo, BLA=Blanco")
        print("ING=Inglés, SUE=Sueco, DAN=Danés, NOR=Noruego, ALE=Alemán")
        print("PER=Perro, GAT=Gato, PAJ=Pájaro, PEZ=Pez, CAB=Caballo")
        print("TE=Té, CAF=Café, LEC=Leche, CER=Cerveza, AGU=Agua")
        print("CHO=chocolate, COO=galletas, PAL=paleta, CAN=caramelos, MAR=malvaviscos")
        
        # Pistas
        print("\nPISTAS DEL ENIGMA:")
        all_clues_valid = True
        board_has_pieces = any(value is not None for value in board_state.values())
        for clue in self.clues:
            result = clue.validate(board_state)
            if result is True:
                status = "✓"
            elif result is False or board_has_pieces:
                status = "✗"
                all_clues_valid = False
            else:
                status = " "
            print(f"{clue.clue_id}. [{status}] {clue.description}")
        
        print("\nOBJETIVO: Descubrir en qué casa vive el dueño que tiene un pez como mascota.")
        
        if all_clues_valid:
            # Encontrar quién tiene el pez
            for col in range(1, 6):
                pet = board_state.get((3, col))
                if pet and pet['attribute']['value'] == 'Pez':
                    nat = board_state.get((2, col))
                    if nat:
                        nationality = nat['attribute']['value']
                        print(f"\n🎉 ¡ENIGMA RESUELTO! El dueño que tiene un pez como mascota es el {nationality}, que vive en la casa ESP{col}.")
                    break
        
        print("="*60 + "\n")
    
    def _broadcast_board_state(self):
        """Envía el estado actual del tablero al frontend y al broker MQTT"""
        board_state = self.db.get_board_state()
        stats = self.db.get_statistics()
        clues = self._evaluate_clues(board_state)

        payload = {
            "type": "board_update",
            "game_state": self.game_state,
            "board": self._serialize_board_for_client(board_state),
            "clues": clues,
            "last_tag": self.last_tag,
            "statistics": stats
        }

        self.mqtt.publish("guardian/game/state", json.dumps(payload, ensure_ascii=False))
        self._emit_frontend_event("game_state", payload)

    def _serialize_board(self, board_state):
        """Convierte el estado del tablero a un formato serializable"""
        serialized = {}
        for (row, col), data in board_state.items():
            key = f"cell_{row}_{col}"
            if data:
                serialized[key] = {
                    "uid": data["uid"],
                    "attribute": data["attribute"]
                }
            else:
                serialized[key] = None
        return serialized

    def _serialize_board_for_client(self, board_state):
        """Convierte el estado del tablero a un formato fácil de consumir por el frontend"""
        serialized = {}
        for row in range(1, 6):
            row_name = self.ROW_TYPES[row].value
            serialized[row_name] = {}
            for col in range(1, 6):
                cell = board_state.get((row, col))
                serialized[row_name][col] = cell["attribute"]["value"] if cell else None
        return serialized

    def _evaluate_clues(self, board_state):
        board_has_pieces = any(value is not None for value in board_state.values())
        clue_statuses = []
        for clue in self.clues:
            result = clue.validate(board_state)
            if result is True:
                status = True
            elif result is False or board_has_pieces:
                status = False
            else:
                status = None
            clue_statuses.append({
                "id": clue.clue_id,
                "description": clue.description,
                "status": status
            })
        return clue_statuses

    def _check_win_condition(self):
        """Verifica si el juego está completado correctamente"""
        if not self.db.is_complete():
            return  # Tablero no está lleno
        
        # Verificar si todas las pistas se cumplen
        board_state = self.db.get_board_state()
        all_clues_valid = True
        
        for clue in self.clues:
            if not clue.validate(board_state):
                all_clues_valid = False
                break
        
        if all_clues_valid:
            self.game_state = "completed"
            msg = "¡JUEGO COMPLETADO! ¡Enigma del Einstein resuelto!"
            self._log(f"[LOGIC] {msg}")
            self.mqtt.publish("guardian/game/completed", msg)
            self._broadcast_board_state()  # Enviar actualización de estado al frontend
        else:
            msg = "Tablero lleno pero pistas no se cumplen"
            self._log(f"[LOGIC] {msg}")
            self.mqtt.publish("guardian/system/log", msg)
    
    def get_game_status(self):
        """Retorna el estado actual del juego"""
        board_state = self.db.get_board_state()
        return {
            "game_state": self.game_state,
            "board": self._serialize_board_for_client(board_state),
            "clues": self._evaluate_clues(board_state),
            "last_tag": self.last_tag,
            "statistics": self.db.get_statistics()
        }
    
    def reset_game(self):
        """Reinicia el juego"""
        self.db.reset_board()
        self._prepare_new_puzzle()
        self.game_state = "running"
        self._broadcast_board_state()
        self._print_board()  # Mostrar tablero vacío en terminal
        self._log("[LOGIC] Juego reiniciado")
        self.mqtt.publish("guardian/system/log", "Juego reiniciado")
