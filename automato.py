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

    # --- NOVO MÉTODO ADICIONADO PARA CORRIGIR BUG ---
    def remove_transition(self, src: str, symbol: str, dst: str):
        """Remove um destino específico de uma transição."""
        key = (src, symbol)
        if key in self.transitions:
            self.transitions[key].discard(dst)
            if not self.transitions[key]:
                del self.transitions[key]
    # -------------------------------------------------

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

        P = [self.final_states, self.states - self.final_states]
        W = [self.final_states]

        while W:
            A = W.pop()
            for c in self.alphabet:
                X = {q for q in self.states
                     if self.transitions.get((q, c), set()) & A}
                newP = []
                for Y in P:
                    inter = Y & X
                    diff = Y - X
                    if inter and diff:
                        newP.append(inter)
                        newP.append(diff)
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
                        newP.append(Y)
                P = newP

        newDFA = Automato()
        state_map = {}
        for i, group in enumerate(P):
            if not group: continue
            new_name = f"M{i}"
            for s in group:
                state_map[s] = new_name
            newDFA.add_state(new_name,
                             is_start=self.start_state in group,
                             is_final=bool(self.final_states & group))

        for (src, sym), dsts in self.transitions.items():
            if len(dsts) != 1:
                continue
            dst = next(iter(dsts))
            newDFA.add_transition(state_map[src], sym, state_map[dst])

        return newDFA

    # -------------------------
    # Validação
    # -------------------------
    def is_dfa(self) -> bool:
        """Verifica se é um DFA válido."""
        for (src, sym), dsts in self.transitions.items():
            if len(dsts) != 1: return False
            if sym == EPSILON: return False
        
        # Opcional: checar se todos os estados tem transição para todos os símbolos
        # for s in self.states:
        #     for sym in self.alphabet:
        #         if (s, sym) not in self.transitions: return False
        return True

    # -------------------------
    # Serialização / Exportação
    # -------------------------
    def export_tikz(self) -> str:
        """Gera código LaTeX TikZ para desenhar o autômato."""
        tikz = ["\\documentclass{standalone}",
                "\\usepackage{tikz}",
                "\\usetikzlibrary{automata, positioning}",
                "\\begin{document}",
                "\\begin{tikzpicture}[->, >=stealth', auto, node distance=2cm, semithick]"]

        for s in self.states:
            opts = ["state"]
            if s == self.start_state:
                opts.append("initial")
            if s in self.final_states:
                opts.append("accepting")
            tikz.append(f"\\node[{','.join(opts)}] ({s}) {{$ {s} $}};")

        for (src, sym), dsts in self.transitions.items():
            for dst in dsts:
                label = sym if sym != EPSILON else "\\epsilon"
                tikz.append(f"\\path ({src}) edge node {{$ {label} $}} ({dst});")

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
        for s in data["states"]:
            a.add_state(s, is_start=(s == data["start_state"]),
                        is_final=(s in data["final_states"]))
        for t in data.get("transitions", []):
            for dst in t["dsts"]:
                a.add_transition(t["src"], t["symbol"], dst)
        return a
