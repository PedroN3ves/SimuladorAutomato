from collections import defaultdict
from typing import Dict, Set, Tuple, Optional, List
import json

class MaquinaMoore:
    """
    Representa uma Máquina de Moore.

    A saída de uma Máquina de Moore está associada ao seu estado atual.
    """
    def __init__(self):
        self.states: Set[str] = set()
        self.start_state: Optional[str] = None
        self.input_alphabet: Set[str] = set()
        self.output_alphabet: Set[str] = set()
        # Mapeia estado para seu símbolo de saída
        self.output_function: Dict[str, str] = {}
        # Mapeia (estado_origem, simbolo_entrada) para estado_destino
        self.transitions: Dict[Tuple[str, str], str] = {}

    def add_state(self, state: str, output_symbol: str, is_start: bool = False):
        """Adiciona um novo estado com seu símbolo de saída."""
        self.states.add(state)
        self.output_function[state] = output_symbol
        self.output_alphabet.add(output_symbol)
        if is_start or self.start_state is None:
            self.start_state = state

    def add_transition(self, src: str, input_symbol: str, dst: str):
        """Adiciona uma transição à máquina."""
        if src not in self.states or dst not in self.states:
            raise ValueError(f"Estado de origem '{src}' ou destino '{dst}' não existe.")
        
        self.input_alphabet.add(input_symbol)
        self.transitions[(src, input_symbol)] = dst

    def remove_state(self, state_to_remove: str):
        """Remove um estado e todas as suas transições associadas."""
        if state_to_remove not in self.states:
            return

        self.states.discard(state_to_remove)
        if state_to_remove in self.output_function:
            del self.output_function[state_to_remove]

        if self.start_state == state_to_remove:
            self.start_state = None

        new_transitions = {}
        for (src, in_sym), dst in self.transitions.items():
            if src != state_to_remove and dst != state_to_remove:
                new_transitions[(src, in_sym)] = dst
        self.transitions = new_transitions

    def rename_state(self, old_name: str, new_name: str):
        """Renomeia um estado em toda a estrutura da máquina."""
        if old_name not in self.states:
            raise ValueError(f"Estado '{old_name}' não existe.")
        if new_name in self.states and new_name != old_name:
            raise ValueError(f"O nome '{new_name}' já está em uso.")

        self.states.remove(old_name)
        self.states.add(new_name)

        if self.start_state == old_name:
            self.start_state = new_name

        self.output_function[new_name] = self.output_function.pop(old_name)

        new_transitions = {}
        for (src, in_sym), dst in self.transitions.items():
            new_src = new_name if src == old_name else src
            new_dst = new_name if dst == old_name else dst
            new_transitions[(new_src, in_sym)] = new_dst
        self.transitions = new_transitions

    def simulate_history(self, input_str: str) -> Tuple[List[Tuple[str, str]], Optional[str]]:
        """
        Simula a execução e retorna o histórico de passos.
        A saída de Moore é baseada no estado, então a saída inicial é a do estado inicial.
        """
        if not self.start_state:
            return [], None

        current_state = self.start_state
        output_str = self.output_function.get(current_state, '')
        history = [(current_state, output_str)]

        for symbol in input_str:
            transition_key = (current_state, symbol)
            if transition_key not in self.transitions:
                return history, None # Máquina trava
            
            next_state = self.transitions[transition_key]
            output_str += self.output_function.get(next_state, '')
            current_state = next_state
            history.append((current_state, output_str))
            
        return history, output_str

    def to_json(self) -> str:
        """Serializa a máquina para uma string JSON."""
        data = {
            "states": list(self.states),
            "start_state": self.start_state,
            "output_function": self.output_function,
            "transitions": [
                {"src": src, "input": in_sym, "dst": dst}
                for (src, in_sym), dst in self.transitions.items()
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'MaquinaMoore':
        """Cria uma Máquina de Moore a partir de uma string JSON."""
        data = json.loads(json_str)
        machine = cls()
        
        output_func = data.get("output_function", {})
        for state, output in output_func.items():
            machine.add_state(state, output, is_start=(state == data.get("start_state")))
        
        for t in data.get("transitions", []):
            machine.add_transition(t["src"], t["input"], t["dst"])
            
        return machine