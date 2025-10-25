from collections import defaultdict
from typing import Dict, Set, Tuple, Optional, List
import json

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
        if is_start or (self.start_state is None and not self.states) : # Define como inicial se for o primeiro
            self.start_state = state
        if is_final:
            self.final_states.add(state)

    def add_transition(self, src: str, input_sym: str, pop_sym: str, dst: str, push_syms: str):
        """
        Adiciona uma transição.
        - input_sym: Símbolo a ser lido da entrada (ou ε, ou multi-caractere como "aa").
        - pop_sym: Símbolo a ser desempilhado (ou ε).
        - push_syms: Símbolos a serem empilhados (ou ε). Empilha da direita para a esquerda (último caractere no topo).
        """
        if src not in self.states or dst not in self.states:
            raise ValueError("Estado de origem ou destino inválido.")

        if input_sym != EPSILON: self.input_alphabet.add(input_sym)
        if pop_sym != EPSILON: self.stack_alphabet.add(pop_sym)
        # Adiciona símbolos individuais de push_syms ao alfabeto da pilha
        for sym in push_syms:
            if sym != EPSILON: self.stack_alphabet.add(sym)

        # Garante que start_stack_symbol esteja no alfabeto da pilha
        self.stack_alphabet.add(self.start_stack_symbol)

        self.transitions[(src, input_sym, pop_sym)].add((dst, push_syms))

    def remove_state(self, state_to_remove: str):
        """Remove um estado e todas as suas transições associadas."""
        if state_to_remove not in self.states:
            return

        self.states.discard(state_to_remove)

        if self.start_state == state_to_remove:
            self.start_state = None

        self.final_states.discard(state_to_remove)

        new_transitions = defaultdict(set)
        for (src, inp, pop), destinations in self.transitions.items():
            if src != state_to_remove:
                # Filtra os destinos que não são para o estado removido
                new_destinations = {d for d in destinations if d[0] != state_to_remove}
                if new_destinations:
                    new_transitions[(src, inp, pop)] = new_destinations
        self.transitions = new_transitions

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

        new_transitions = defaultdict(set)
        for (src, inp, pop), destinations in self.transitions.items():
            new_src = new_name if src == old_name else src
            new_destinations = set()
            for dst, push in destinations:
                new_destinations.add((new_name if dst == old_name else dst, push))
            # Atualiza a chave e o valor
            new_transitions[(new_src, inp, pop)] = new_destinations
        self.transitions = new_transitions
        
    def remove_pda_transition(self, src: str, input_sym: str, pop_sym: str, dst: str, push_syms: str):
        """Remove uma transição específica."""
        key = (src, input_sym, pop_sym)
        target = (dst, push_syms)
        if key in self.transitions:
            self.transitions[key].discard(target)
            if not self.transitions[key]: # Remove a chave se o conjunto ficar vazio
                del self.transitions[key]


    # ***** INÍCIO DAS MODIFICAÇÕES (Multi-caractere) *****
    def simulate_history(self, input_str: str) -> Tuple[List[Tuple[str, int, Tuple]], bool]:
        """
        Simula a execução e retorna o histórico de configurações para animação.
        Modificado para suportar transições com múltiplos caracteres (ex: "aa").

        Retorna (histórico, aceito).
        Histórico é List[Tuple[estado, input_idx_consumido, pilha_como_tupla]]
        """
        if not self.start_state:
            return [], False

        # Configuração: (estado, indice_entrada, pilha_tupla)
        initial_config = (self.start_state, 0, (self.start_stack_symbol,))
        
        # Histórico guarda a primeira configuração viável encontrada após cada consumo de símbolo (ou no início)
        history: List[Tuple[str, int, Tuple]] = []

        # Conjunto de configurações ativas atuais (estado, indice, pilha)
        current_configs = self._get_epsilon_closure({initial_config})
        
        # Guarda o estado inicial no histórico
        if current_configs:
            # Pega uma configuração representativa (a primeira encontrada)
            rep_state, rep_idx, rep_stack = next(iter(current_configs))
            history.append((rep_state, rep_idx, rep_stack))
        else:
             history.append(("-", 0, tuple())) # Caso inicial impossível

        processed_indices = {0} # Índices já processados para evitar reprocessamento infinito com epsilon
        
        # Usa uma fila para busca em largura nas configurações possíveis
        queue = list(current_configs)
        
        final_reachable_configs = set() # Configurações alcançadas após consumir toda a entrada

        visited_in_step = set() # Evita loops infinitos de epsilon no mesmo passo

        while queue:
            # Pega a próxima configuração para explorar
            current_state, current_idx, current_stack = queue.pop(0)

            # Se já consumiu toda a entrada, adiciona aos finais e continua (pode haver epsilons)
            if current_idx == len(input_str):
                final_reachable_configs.add((current_state, current_idx, current_stack))
                # Ainda processa epsilons a partir daqui
            
            config_tuple = (current_state, current_idx, current_stack)
            if config_tuple in visited_in_step: continue
            visited_in_step.add(config_tuple)


            # --- 1. Tentar consumir símbolos da entrada ---
            remaining_input = input_str[current_idx:]
            if remaining_input:
                # Encontra todos os símbolos de input possíveis (não-epsilon) que saem do estado atual
                possible_symbols = set()
                for (src, sym, pop) in self.transitions.keys():
                    if src == current_state and sym != EPSILON:
                        possible_symbols.add(sym)
                
                # Ordena do mais longo para o mais curto
                sorted_symbols = sorted(list(possible_symbols), key=len, reverse=True)

                moved_with_symbol = False
                for symbol in sorted_symbols:
                    if remaining_input.startswith(symbol):
                        # Encontrou uma transição que consome o símbolo 'symbol'
                        
                        # Calcula as próximas configurações após consumir 'symbol'
                        next_configs_after_move = self._move_with_symbol(
                            {(current_state, current_idx, current_stack)}, # Apenas a config atual
                            symbol
                        )
                        
                        # Calcula o fecho-epsilon dessas novas configurações
                        closure_after_move = self._get_epsilon_closure(next_configs_after_move)

                        new_idx = current_idx + len(symbol)

                        # Adiciona novas configurações à fila e ao histórico se o índice avançou
                        if new_idx not in processed_indices:
                             if closure_after_move:
                                rep_state, rep_idx_actual, rep_stack = next(iter(closure_after_move))
                                # Usa new_idx no histórico, pois representa o consumo até este ponto
                                history.append((rep_state, new_idx, rep_stack)) 
                                processed_indices.add(new_idx)
                                visited_in_step.clear() # Limpa visitados para o novo índice
                        
                        for conf in closure_after_move:
                             if conf not in queue and conf not in visited_in_step: # Evita adicionar duplicatas na fila
                                queue.append(conf)

                        moved_with_symbol = True
                        break # Processou a transição mais longa possível, vai para a próxima config da fila
            
            # --- 2. Processar transições Epsilon (mesmo se consumiu símbolo ou se chegou ao fim) ---
            # Calcula o fecho epsilon APENAS da configuração atual para adicionar à fila
            # Nota: _get_epsilon_closure já lida com pop/push de epsilon
            epsilon_neighbors = self._get_epsilon_closure({(current_state, current_idx, current_stack)})
            
            for conf in epsilon_neighbors:
                 # Adiciona apenas se for diferente da config atual e não estiver já na fila/visitado
                 if conf != config_tuple and conf not in queue and conf not in visited_in_step:
                     queue.append(conf)
                     # Se chegou ao fim da entrada via epsilon, também é final
                     if conf[1] == len(input_str):
                         final_reachable_configs.add(conf)


        # Após o loop, verifica a aceitação
        accepted = any(c_state in self.final_states for c_state, c_idx, _ in final_reachable_configs if c_idx == len(input_str))

        # Garante que o histórico tenha pelo menos o estado inicial
        if not history:
             history.append((self.start_state if self.start_state else "-", 0, (self.start_stack_symbol,)))

        # Ajusta o histórico para ter o formato correto (estado, indice, pilha)
        # Se a máquina travou, o último item do histórico pode não ter o índice correto
        final_history = []
        last_idx = 0
        for state, idx, stack in history:
            final_history.append((state, idx, stack))
            last_idx = idx
            
        # Se travou antes do fim, adiciona um estado de "trava"
        if last_idx < len(input_str) and not accepted:
             # Pega a última pilha válida registrada
             last_valid_stack = final_history[-1][2] if final_history else tuple()
             final_history.append(("-", last_idx, last_valid_stack)) # Estado '-' indica trava

        return final_history, accepted


    def _get_epsilon_closure(self, configs: Set[Tuple[str, int, Tuple]]) -> Set[Tuple[str, int, Tuple]]:
        """Calcula o fecho-epsilon de um conjunto de configurações (estado, indice, pilha)."""
        closure = set(configs)
        queue = list(configs)
        
        visited_epsilon = set() # Evita loops infinitos de epsilon

        while queue:
            state, input_idx, stack = queue.pop(0)
            
            config_key = (state, stack) # Chave para visited_epsilon não depende do índice
            if config_key in visited_epsilon: continue
            visited_epsilon.add(config_key)

            # Transições ε que não desempilham (lê ε, desempilha ε)
            key = (state, EPSILON, EPSILON)
            for next_state, push_syms in self.transitions.get(key, set()):
                # Empilha da direita para a esquerda (último caractere no topo)
                new_stack = stack + tuple(push_syms) if push_syms != EPSILON else stack
                new_config = (next_state, input_idx, new_stack)
                if new_config not in closure:
                    closure.add(new_config)
                    queue.append(new_config)
                    # Se adicionou, remove dos visitados para permitir re-exploração de outro caminho
                    visited_epsilon.discard((next_state, new_stack)) 
            
            # Transições ε que desempilham (lê ε, desempilha topo)
            top = stack[-1] if stack else None
            if top:
                key = (state, EPSILON, top)
                for next_state, push_syms in self.transitions.get(key, set()):
                    stack_base = stack[:-1]
                    # Empilha da direita para a esquerda
                    new_stack = stack_base + tuple(push_syms) if push_syms != EPSILON else stack_base
                    new_config = (next_state, input_idx, new_stack)
                    if new_config not in closure:
                        closure.add(new_config)
                        queue.append(new_config)
                        visited_epsilon.discard((next_state, new_stack))
        return closure

    def _move_with_symbol(self, configs: Set[Tuple[str, int, Tuple]], symbol: str) -> Set[Tuple[str, int, Tuple]]:
        """Processa transições para um símbolo de entrada específico (pode ser multi-caractere)."""
        next_configs = set()
        symbol_len = len(symbol)

        for state, input_idx, stack in configs:
            
            new_input_idx = input_idx + symbol_len # Novo índice após consumir o símbolo
            
            # Transições que não desempilham (lê symbol, desempilha ε)
            key = (state, symbol, EPSILON)
            for next_state, push_syms in self.transitions.get(key, set()):
                 # Empilha da direita para a esquerda
                new_stack = stack + tuple(push_syms) if push_syms != EPSILON else stack
                next_configs.add((next_state, new_input_idx, new_stack))

            # Transições que desempilham (lê symbol, desempilha topo)
            top = stack[-1] if stack else None
            if top:
                key = (state, symbol, top)
                for next_state, push_syms in self.transitions.get(key, set()):
                    stack_base = stack[:-1]
                     # Empilha da direita para a esquerda
                    new_stack = stack_base + tuple(push_syms) if push_syms != EPSILON else stack_base
                    next_configs.add((next_state, new_input_idx, new_stack))
        return next_configs
    # ***** FIM DAS MODIFICAÇÕES *****


    def simulate(self, input_str: str) -> bool:
        """
        Simula a execução do autômato de pilha.
        Retorna True se a cadeia é aceita, False caso contrário.
        """
        if not self.start_state:
            return False

        # A nova simulate_history lida com a lógica de aceitação
        _, accepted = self.simulate_history(input_str)
        return accepted

    def to_json(self) -> str:
        """Serializa o autômato para uma string JSON."""
        serializable_transitions = {}
        for (src, inp, pop_sym), dests in self.transitions.items():
            key = f"{src},{inp},{pop_sym}"
            # Converte tuplas internas para listas para serem serializáveis
            serializable_transitions[key] = [list(d) for d in dests]

        # Filtra alfabetos para garantir que sejam listas de strings
        input_alpha = list(filter(lambda x: isinstance(x, str), self.input_alphabet))
        stack_alpha = list(filter(lambda x: isinstance(x, str), self.stack_alphabet))


        data = {
            "states": list(self.states),
            "input_alphabet": input_alpha,
            "stack_alphabet": stack_alpha,
            "start_state": self.start_state,
            "start_stack_symbol": self.start_stack_symbol,
            "final_states": list(self.final_states),
            "transitions": serializable_transitions,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'AutomatoPilha':
        """Cria um Autômato de Pilha a partir de uma string JSON."""
        data = json.loads(json_str)
        pda = cls()
        pda.states = set(data.get("states", []))
        pda.input_alphabet = set(data.get("input_alphabet", []))
        pda.stack_alphabet = set(data.get("stack_alphabet", []))
        pda.start_state = data.get("start_state")
        pda.start_stack_symbol = data.get("start_stack_symbol", 'Z')
        pda.final_states = set(data.get("final_states", []))
        
        # Garante que start_stack_symbol esteja no alfabeto
        if pda.start_stack_symbol:
             pda.stack_alphabet.add(pda.start_stack_symbol)

        for key, dests in data.get("transitions", {}).items():
            try:
                parts = key.split(',', 2)
                if len(parts) == 3:
                    src, inp, pop_sym = parts
                    # Converte listas de volta para tuplas ao carregar
                    pda.transitions[(src, inp, pop_sym)] = {tuple(d) for d in dests}
                     # Adiciona símbolos aos alfabetos (redundante se add_transition for chamado, mas seguro)
                    if inp != EPSILON: pda.input_alphabet.add(inp)
                    if pop_sym != EPSILON: pda.stack_alphabet.add(pop_sym)
                    for _, push_list in dests:
                        for char in push_list:
                             if char != EPSILON: pda.stack_alphabet.add(char)

                else:
                    print(f"Aviso: Ignorando chave de transição malformada: {key}")
            except Exception as e:
                 print(f"Aviso: Erro ao processar transição {key} -> {dests}: {e}")

        # Garante que start_state é válido
        if pda.start_state not in pda.states:
            if pda.states:
                pda.start_state = next(iter(pda.states))
                print(f"Aviso: Estado inicial '{data.get('start_state')}' não encontrado. Definindo '{pda.start_state}' como inicial.")
            else:
                 pda.start_state = None


        return pda

def snapshot_of_pda(automato: AutomatoPilha, positions: Dict[str, Tuple[int, int]]) -> str:
    """Retorna JSON serializável representando o estado completo (autômato + posições)."""
    data = {
        "automato": json.loads(automato.to_json()),
        "positions": positions
    }
    return json.dumps(data, ensure_ascii=False)

def restore_from_pda_snapshot(s: str) -> Tuple[AutomatoPilha, Dict[str, Tuple[int, int]]]:
    """Restaura um autômato de pilha e suas posições a partir de um snapshot JSON."""
    data = json.loads(s)
    
    # Garante que o objeto do autômato seja um dicionário antes de passar para from_json
    automato_data = data.get("automato", {})
    if isinstance(automato_data, str):
        automato_data = json.loads(automato_data)

    automato = AutomatoPilha.from_json(json.dumps(automato_data))
    positions = data.get("positions", {})
    return automato, positions