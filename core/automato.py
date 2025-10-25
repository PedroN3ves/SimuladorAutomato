from collections import defaultdict, deque
from typing import Dict, Set, Tuple, List, Optional
import json

EPSILON = "&"


class Automato:
    def __init__(self):
        self.states: Set[str] = set()
        self.start_state: Optional[str] = None
        self.final_states: Set[str] = set()
        self.transitions: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
        self.alphabet: Set[str] = set()

    # -------------------------
    # Manipulação de estados e transições
    # -------------------------
    def add_state(self, state: str, is_start=False, is_final=False):
        self.states.add(state)
        if is_start or self.start_state is None:
            self.start_state = state
        if is_final:
            self.final_states.add(state)

    def add_transition(self, src: str, symbol: str, dst: str):
        if src not in self.states or dst not in self.states:
            raise ValueError("Estado inexistente.")
        if symbol != EPSILON:
            self.alphabet.add(symbol)
        self.transitions[(src, symbol)].add(dst)

    def remove_state(self, state_to_remove: str):
        """Remove um estado e todas as suas transições associadas."""
        if state_to_remove not in self.states:
            return

        self.states.discard(state_to_remove)

        if self.start_state == state_to_remove:
            self.start_state = None

        self.final_states.discard(state_to_remove)

        new_transitions = defaultdict(set)
        for (src, sym), dsts in self.transitions.items():
            if src != state_to_remove:
                new_dsts = dsts - {state_to_remove}
                if new_dsts:
                    new_transitions[(src, sym)] = new_dsts
        
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
        for (src, sym), dsts in self.transitions.items():
            new_src = new_name if src == old_name else src
            new_dsts = {new_name if d == old_name else d for d in dsts}
            new_transitions[(new_src, sym)] = new_dsts
        self.transitions = new_transitions

    # --- NOVO MÉTODO ADICIONADO ---
    def remove_transition(self, src: str, symbol: str, dst: str):
        """Remove um destino específico de uma transição."""
        key = (src, symbol)
        if key in self.transitions:
            self.transitions[key].discard(dst)
            # Se o conjunto de destinos ficar vazio, remove a entrada do dicionário
            if not self.transitions[key]:
                del self.transitions[key]
    # -----------------------------

    # -------------------------
    # Simulação
    # -------------------------
    def epsilon_closure(self, states: Set[str]) -> Set[str]:
        """Calcula o fecho-ε de um conjunto de estados."""
        closure = set(states)
        stack = list(states)
        while stack:
            state = stack.pop()
            for nxt in self.transitions.get((state, EPSILON), []):
                if nxt not in closure:
                    closure.add(nxt)
                    stack.append(nxt)
        return closure

    def move(self, states: Set[str], symbol: str) -> Set[str]:
        nxt_states = set()
        for s in states:
            nxt_states |= self.transitions.get((s, symbol), set())
        return nxt_states

    # ***** INÍCIO DA MODIFICAÇÃO (Multi-caractere) *****
    def simulate_history(self, input_str: str):
        """
        Simula e retorna histórico de passos (para animação).
        Modificado para suportar transições com múltiplos caracteres (ex: "aa").
        """
        if not self.start_state:
            return [], False

        # O histórico armazena (conjunto_de_estados, indice_de_entrada_consumido)
        current_states = self.epsilon_closure({self.start_state})
        history = [(set(current_states), 0)]
        
        input_idx = 0
        
        # Caso especial: entrada vazia
        if not input_str:
            accepted = any(s in self.final_states for s in current_states)
            return history, accepted

        # Loop principal baseado no índice da string, não em caracteres
        while input_idx < len(input_str):
            
            # 1. Encontra todas as transições *não-epsilon* que podem ser tomadas
            
            # Coleta todos os símbolos de transição (ex: "a", "b", "aa", "aba")
            # que saem dos estados ativos atuais
            possible_symbols = set()
            for s in current_states:
                for (src, sym) in self.transitions.keys():
                    if src == s and sym != EPSILON:
                        possible_symbols.add(sym)
            
            # Ordena os símbolos do mais longo para o mais curto
            # Isso garante que "aa" seja tentado antes de "a"
            sorted_symbols = sorted(list(possible_symbols), key=len, reverse=True)
            
            consumed_input = False
            next_states_set = set()
            remaining_input = input_str[input_idx:]
            
            # 2. Tenta encontrar a transição mais longa que corresponde à fita
            for symbol in sorted_symbols:
                if remaining_input.startswith(symbol):
                    # Esta é uma transição válida.
                    
                    # Esta é a lógica da função 'move' para este símbolo
                    for s in current_states:
                        next_states_set.update(self.transitions.get((s, symbol), set()))
                    
                    if next_states_set:
                        input_idx += len(symbol) # Avança o ponteiro da fita
                        consumed_input = True
                        break # Para de verificar (já pegamos a transição mais longa)
            
            if not consumed_input:
                # Nenhuma transição (nem "a", nem "aa", etc.) correspondeu
                # ao início da fita. A máquina trava.
                break
            
            # 3. Se moveu, calcula o fecho-epsilon dos novos estados
            current_states = self.epsilon_closure(next_states_set)
            history.append((set(current_states), input_idx))

            if not current_states:
                 # Se o fecho-epsilon for vazio (ex: moveu para um estado sem saída), trava.
                 break
        
        # Fim do loop. Verifica aceitação.
        # Aceita se consumiu EXATAMENTE a entrada E está em um estado final
        accepted = (input_idx == len(input_str)) and any(s in self.final_states for s in current_states)
        
        return history, accepted

    def simulate(self, input_str: str) -> bool:
        """Simulação simples sem histórico."""
        # A nova simulate_history já calcula a aceitação corretamente
        _, accepted = self.simulate_history(input_str)
        return accepted
    # ***** FIM DA MODIFICAÇÃO *****

    # -------------------------
    # Conversão AFND → AFD
    # -------------------------
    def to_dfa(self):
        if not self.start_state:
            return None

        dfa = Automato()
        start_closure = frozenset(self.epsilon_closure({self.start_state}))
        unmarked = deque([start_closure])
        state_map = {start_closure: "q0"}
        dfa.add_state("q0", is_start=True,
                      is_final=any(s in self.final_states for s in start_closure))

        count = 1
        
        # IMPORTANTE: A conversão para AFD assume que o alfabeto
        # é composto de *caracteres únicos*. Se o seu AFND
        # usa "aa", a conversão para AFD padrão não funcionará
        # corretamente. Ela tratará "aa" como dois símbolos "a".
        # Para esta implementação, vamos assumir que a conversão
        # só funciona com alfabetos de símbolos únicos.
        
        # Coleta o alfabeto de símbolos únicos
        single_char_alphabet = set()
        for sym in self.alphabet:
            for char in sym:
                single_char_alphabet.add(char)

        while unmarked:
            T = unmarked.popleft()
            T_name = state_map[T]
            for sym in single_char_alphabet: # Usa alfabeto de char único
                if sym == EPSILON:
                    continue
                
                # A função move precisa ser chamada para o símbolo de char único
                U = frozenset(self.epsilon_closure(self.move(T, sym)))
                
                if not U:
                    continue
                if U not in state_map:
                    state_map[U] = f"q{count}"
                    dfa.add_state(state_map[U],
                                  is_final=any(s in self.final_states for s in U))
                    unmarked.append(U)
                    count += 1
                dfa.add_transition(T_name, sym, state_map[U])
        return dfa

    # -------------------------
    # Minimização de AFD
    # -------------------------
    def minimize(self):
        """Minimiza AFD pelo algoritmo de partições."""
        if not self.is_dfa():
            raise ValueError("A minimização requer um AFD válido.")

        # Garante que o AFD é completo
        self._make_complete()

        P = [self.final_states, self.states - self.final_states]
        W = [self.final_states] if len(self.final_states) <= len(self.states - self.final_states) else [self.states - self.final_states]


        while W:
            A = W.pop(0)
            for c in self.alphabet:
                X = {q for q in self.states if self.transitions.get((q, c), set()) and next(iter(self.transitions.get((q,c), set())), None) in A}

                new_P = []
                for Y in P:
                    inter = Y & X
                    diff = Y - X
                    if inter and diff:
                        new_P.append(inter)
                        new_P.append(diff)
                        if Y in W:
                            W.remove(Y)
                            W.append(inter)
                            W.append(diff)
                        else:
                            if len(inter) <= len(diff):
                                W.append(inter)
                            else:
                                W.append(diff)
                    else:
                        new_P.append(Y)
                P = new_P

        # Remove o estado de erro, se existir
        error_state_name = "_error"
        if error_state_name in self.states:
            self.remove_state(error_state_name)
            # Refaz as partições sem o estado de erro
            P = [p - {error_state_name} for p in P if p - {error_state_name}]


        newDFA = Automato()
        state_map = {}
        
        # Filtra grupos vazios que podem surgir da remoção do estado de erro
        P = [group for group in P if group]

        for i, group in enumerate(P):
            if not group: continue
            
            # Escolhe um nome de estado representativo (o primeiro em ordem alfabética)
            rep_name = sorted(list(group))[0]
            new_name = f"{{{','.join(sorted(list(group)))}}}" if len(group) > 1 else rep_name
            
            for s in group:
                state_map[s] = new_name
            
            newDFA.add_state(new_name,
                             is_start=self.start_state in group,
                             is_final=bool(self.final_states & group))

        # Adiciona transições ao novo AFD
        processed_transitions = set()
        for (src, sym), dsts in self.transitions.items():
            if src in state_map and (state_map[src], sym) not in processed_transitions:
                dst = next(iter(dsts)) # É um DFA, então só há um destino
                if dst in state_map:
                    newDFA.add_transition(state_map[src], sym, state_map[dst])
                    processed_transitions.add((state_map[src], sym))

        return newDFA

    def _make_complete(self):
        """Adiciona um estado de erro para tornar o AFD completo, se necessário."""
        error_state_name = "_error"
        has_incomplete_transitions = False
        
        # Minimização também só funciona com alfabeto de char único
        single_char_alphabet = set()
        for sym in self.alphabet:
            for char in sym:
                single_char_alphabet.add(char)

        for s in self.states:
            for sym in single_char_alphabet:
                if not self.transitions.get((s, sym)):
                    has_incomplete_transitions = True
                    break
            if has_incomplete_transitions:
                break
        
        if has_incomplete_transitions:
            self.add_state(error_state_name)
            for s in list(self.states): # Itera sobre uma cópia
                 for sym in single_char_alphabet:
                    if not self.transitions.get((s,sym)):
                        self.add_transition(s, sym, error_state_name)


    # -------------------------
    # Validação
    # -------------------------
    def is_dfa(self) -> bool:
        """Verifica se é um AFD válido."""
        for (src, sym), dsts in self.transitions.items():
            if len(dsts) != 1: return False
            if sym == EPSILON: return False
            # Um DFA verdadeiro não deve ter símbolos multi-caractere
            if len(sym) > 1: return False 
        
        return True

    # -------------------------
    # Serialização / Exportação
    # -------------------------
    def export_tikz(self) -> str:
        """Gera código LaTeX TikZ para desenhar o autômato."""
        tikz = ["\\documentclass{standalone}",
                "\\usepackage{tikz}",
                "\\usetikzlibrary{automata, positioning, arrows}",
                "\\begin{document}",
                "\\begin{tikzpicture}[->, >=stealth', auto, node distance=2.8cm, semithick]"]

        # Define posições para evitar sobreposição (layout simples)
        # Este é um layout de exemplo, a GUI usa posições definidas pelo usuário
        nodes = sorted(list(self.states))
        for i, s in enumerate(nodes):
            opts = ["state"]
            if s == self.start_state:
                opts.append("initial")
            if s in self.final_states:
                opts.append("accepting")
            
            # Escapa caracteres especiais para o LaTeX
            display_s = s.replace("_", "\\_")
            tikz.append(f"\\node[{','.join(opts)}] ({s}) [right of=q{i-1} if i > 0 else base] {{${display_s}$}};")

        # Agrupa transições para arcos curvos ou laços
        edge_labels = defaultdict(list)
        for (src, sym), dsts in self.transitions.items():
            for dst in dsts:
                edge_labels[(src, dst)].append(sym)
        
        for (src, dst), symbols in edge_labels.items():
            # Escapa símbolos para LaTeX (ex: "aa" vira "aa", "&" vira \epsilon)
            processed_symbols = []
            for s in sorted(symbols):
                if s == EPSILON:
                    processed_symbols.append("\\epsilon")
                else:
                    processed_symbols.append(s.replace("_", "\\_"))

            label = ",".join(processed_symbols)

            if src == dst:
                tikz.append(f"\\path ({src}) edge [loop above] node {{${label}$}} ();")
            else:
                # Verifica se existe uma transição de volta para curvar o arco
                if (dst, src) in edge_labels:
                    tikz.append(f"\\path ({src}) edge [bend left] node {{${label}$}} ({dst});")
                else:
                    tikz.append(f"\\path ({src}) edge node {{${label}$}} ({dst});")


        tikz.append("\\end{tikzpicture}")
        tikz.append("\\end{document}")
        return "\n".join(tikz)

    def to_json(self) -> str:
        data = {
            "states": list(self.states),
            "start_state": self.start_state,
            "final_states": list(self.final_states),
            "alphabet": list(self.alphabet),
            "transitions": [
                {"src": src, "symbol": sym, "dsts": list(dsts)}
                for (src, sym), dsts in self.transitions.items()
            ],
        }
        return json.dumps(data, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str):
        data = json.loads(json_str)
        a = cls()
        a.states = set(data.get("states", []))
        a.start_state = data.get("start_state")
        a.final_states = set(data.get("final_states", []))
        a.alphabet = set(data.get("alphabet", []))
        
        transitions_data = data.get("transitions", [])
        a.transitions = defaultdict(set)
        for t in transitions_data:
            src = t["src"]
            sym = t["symbol"]
            for dst in t["dsts"]:
                a.transitions[(src, sym)].add(dst)
        return a