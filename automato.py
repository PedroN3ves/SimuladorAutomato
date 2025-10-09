from collections import defaultdict, deque
from typing import Dict, Set, Tuple, List, Optional
import json

EPSILON = "ε"


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

    def simulate_history(self, input_str: str):
        """Simula e retorna histórico de passos (para animação)."""
        if not self.start_state:
            return [], False
        current = self.epsilon_closure({self.start_state})
        history = [(set(current), 0)]
        for i, symbol in enumerate(input_str, 1):
            current = self.epsilon_closure(self.move(current, symbol))
            history.append((set(current), i))
        accepted = any(s in self.final_states for s in current)
        return history, accepted

    def simulate(self, input_str: str) -> bool:
        """Simulação simples sem histórico."""
        _, accepted = self.simulate_history(input_str)
        return accepted

    # -------------------------
    # Conversão NFA → DFA
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
        while unmarked:
            T = unmarked.popleft()
            T_name = state_map[T]
            for sym in self.alphabet:
                if sym == EPSILON:
                    continue
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
    # Minimização de DFA
    # -------------------------
    def minimize(self):
        """Minimiza DFA pelo algoritmo de partições."""
        if not self.is_dfa():
            raise ValueError("A minimização requer um DFA válido.")

        # Garante que o DFA é completo
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

        # Adiciona transições ao novo DFA
        processed_transitions = set()
        for (src, sym), dsts in self.transitions.items():
            if src in state_map and (state_map[src], sym) not in processed_transitions:
                dst = next(iter(dsts)) # É um DFA, então só há um destino
                if dst in state_map:
                    newDFA.add_transition(state_map[src], sym, state_map[dst])
                    processed_transitions.add((state_map[src], sym))

        return newDFA

    def _make_complete(self):
        """Adiciona um estado de erro para tornar o DFA completo, se necessário."""
        error_state_name = "_error"
        has_incomplete_transitions = False
        for s in self.states:
            for sym in self.alphabet:
                if not self.transitions.get((s, sym)):
                    has_incomplete_transitions = True
                    break
            if has_incomplete_transitions:
                break
        
        if has_incomplete_transitions:
            self.add_state(error_state_name)
            for s in list(self.states): # Itera sobre uma cópia
                 for sym in self.alphabet:
                    if not self.transitions.get((s,sym)):
                        self.add_transition(s, sym, error_state_name)


    # -------------------------
    # Validação
    # -------------------------
    def is_dfa(self) -> bool:
        """Verifica se é um DFA válido."""
        for (src, sym), dsts in self.transitions.items():
            if len(dsts) != 1: return False
            if sym == EPSILON: return False
        
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
            label = ",".join(sorted(symbols)).replace(EPSILON, "\\epsilon")
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
