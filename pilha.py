from collections import defaultdict
from typing import Dict, Set, Tuple, Optional, List

EPSILON = "&"

class AutomatoPilha:
    """
    Representa um Autômato de Pilha (Pushdown Automaton - PDA).
    """
    def __init__(self):
        self.states: Set[str] = set()
        self.input_alphabet: Set[str] = set()
        self.stack_alphabet: Set[str] = set()
        self.start_state: Optional[str] = None
        self.start_stack_symbol: str = 'Z'
        self.final_states: Set[str] = set()
        # Mapeia (estado, simbolo_entrada, simbolo_pilha_topo) para um conjunto de (novo_estado, simbolos_a_empilhar)
        self.transitions: Dict[Tuple[str, str, str], Set[Tuple[str, str]]] = defaultdict(set)

    def add_state(self, state: str, is_start: bool = False, is_final: bool = False):
        self.states.add(state)
        if is_start:
            self.start_state = state
        if is_final:
            self.final_states.add(state)

    def add_transition(self, src: str, input_sym: str, pop_sym: str, dst: str, push_syms: str):
        """
        Adiciona uma transição.
        - input_sym: Símbolo a ser lido da entrada (ou ε).
        - pop_sym: Símbolo a ser desempilhado (ou ε).
        - push_syms: Símbolos a serem empilhados (ou ε).
        """
        if src not in self.states or dst not in self.states:
            raise ValueError("Estado de origem ou destino inválido.")

        if input_sym != EPSILON: self.input_alphabet.add(input_sym)
        if pop_sym != EPSILON: self.stack_alphabet.add(pop_sym)
        for sym in push_syms:
            if sym != EPSILON: self.stack_alphabet.add(sym)

        self.transitions[(src, input_sym, pop_sym)].add((dst, push_syms))

    def rename_state(self, old_name: str, new_name: str):
        """Renomeia um estado em toda a estrutura do autômato."""
        if old_name not in self.states:
            raise ValueError(f"Estado '{old_name}' não existe.")
        if new_name in self.states and new_name != old_name:
            raise ValueError(f"O nome '{new_name}' já está em uso.")

        self.states.remove(old_name)
        self.states.add(new_name)

        if self.start_state == old_name:
            self.start_state = new_name
        
        if old_name in self.final_states:
            self.final_states.remove(old_name)
            self.final_states.add(new_name)

        # A lógica de atualização das transições é mais complexa e precisa ser implementada
        # Por enquanto, focamos na renomeação nos conjuntos de estados.

    def simulate_history(self, input_str: str) -> Tuple[List[Tuple[str, str, Tuple]], bool]:
        """
        Simula a execução e retorna o histórico de configurações para animação.
        Retorna (histórico, aceito).
        """
        if not self.start_state:
            return [], False

        # Uma configuração é (estado, cadeia_restante, pilha_como_tupla)
        initial_config = (self.start_state, input_str, (self.start_stack_symbol,))
        
        # O histórico guardará a primeira configuração viável a cada passo
        history: List[Tuple[str, str, Tuple]] = []

        # Processa o estado inicial e seu fecho-epsilon
        current_configs = self._get_epsilon_closure({initial_config})
        history.append(list(current_configs)[0] if current_configs else ("-", input_str, tuple()))

        for i, symbol in enumerate(input_str):
            # Move com o símbolo atual a partir de todas as configurações atuais
            next_configs_after_move = self._move_with_symbol(current_configs, symbol)
            
            # Calcula o fecho-epsilon das novas configurações
            current_configs = self._get_epsilon_closure(next_configs_after_move)

            if not current_configs:
                # A máquina travou
                history.append(("-", input_str[i+1:], tuple()))
                break
            
            history.append(list(current_configs)[0])

        # Verifica a aceitação a partir do último conjunto de configurações alcançáveis
        accepted = any(c_state in self.final_states for c_state, _, _ in current_configs)
        return history, accepted

    def _get_epsilon_closure(self, configs: Set[Tuple[str, str, Tuple]]) -> Set[Tuple[str, str, Tuple]]:
        """Calcula o fecho-epsilon de um conjunto de configurações."""
        closure = set(configs)
        queue = list(configs)
        
        while queue:
            state, rem_input, stack = queue.pop(0)
            
            # Transições ε que não desempilham
            for next_state, push_syms in self.transitions.get((state, EPSILON, EPSILON), set()):
                new_stack = stack + tuple(reversed(push_syms)) if push_syms != EPSILON else stack
                new_config = (next_state, rem_input, new_stack)
                if new_config not in closure:
                    closure.add(new_config)
                    queue.append(new_config)
            
            # Transições ε que desempilham
            top = stack[-1] if stack else None
            if top:
                for next_state, push_syms in self.transitions.get((state, EPSILON, top), set()):
                    new_stack = stack[:-1] + tuple(reversed(push_syms)) if push_syms != EPSILON else stack[:-1]
                    new_config = (next_state, rem_input, new_stack)
                    if new_config not in closure:
                        closure.add(new_config)
                        queue.append(new_config)
        return closure

    def _move_with_symbol(self, configs: Set[Tuple[str, str, Tuple]], symbol: str) -> Set[Tuple[str, str, Tuple]]:
        """Processa transições para um símbolo de entrada específico."""
        next_configs = set()
        for state, rem_input, stack in configs:
            if not rem_input or rem_input[0] != symbol:
                continue

            new_rem_input = rem_input[1:]
            
            # Transições que não desempilham
            for next_state, push_syms in self.transitions.get((state, symbol, EPSILON), set()):
                new_stack = stack + tuple(reversed(push_syms)) if push_syms != EPSILON else stack
                next_configs.add((next_state, new_rem_input, new_stack))

            # Transições que desempilham
            top = stack[-1] if stack else None
            if top:
                for next_state, push_syms in self.transitions.get((state, symbol, top), set()):
                    new_stack = stack[:-1] + tuple(reversed(push_syms)) if push_syms != EPSILON else stack[:-1]
                    next_configs.add((next_state, new_rem_input, new_stack))
        return next_configs

    def simulate(self, input_str: str) -> bool:
        """
        Simula a execução do autômato de pilha.
        Retorna True se a cadeia é aceita, False caso contrário.
        Usa busca em largura para lidar com o não-determinismo.
        """
        if not self.start_state:
            return False

        # A simulação completa é mais complexa devido ao não-determinismo.
        # Para uma verificação simples, usamos o histórico.
        history, accepted = self.simulate_history(input_str)
        return accepted