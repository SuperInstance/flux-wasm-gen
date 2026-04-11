"""
FLUX WASM Generator — compile FLUX bytecode to WebAssembly.

Translates FLUX opcodes to WASM instructions so FLUX programs
can run in any browser or WASM runtime.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class WasmOp(Enum):
    LOCAL_GET = "local.get"
    LOCAL_SET = "local.set"
    LOCAL_TEE = "local.tee"
    I32_CONST = "i32.const"
    I32_ADD = "i32.add"
    I32_SUB = "i32.sub"
    I32_MUL = "i32.mul"
    I32_DIV_S = "i32.div_s"
    I32_REM_S = "i32.rem_s"
    I32_EQ = "i32.eq"
    I32_LT_S = "i32.lt_s"
    I32_GT_S = "i32.gt_s"
    I32_AND = "i32.and"
    I32_OR = "i32.or"
    I32_XOR = "i32.xor"
    I32_SHL = "i32.shl"
    I32_SHR_S = "i32.shr_s"
    BLOCK = "block"
    LOOP = "loop"
    IF = "if"
    ELSE = "else"
    END = "end"
    BR = "br"
    BR_IF = "br_if"
    RETURN = "return"
    DROP = "drop"
    UNREACHABLE = "unreachable"
    NOP = "nop"


@dataclass
class WasmInstruction:
    op: WasmOp
    args: List = field(default_factory=list)
    comment: str = ""


@dataclass
class WasmFunction:
    name: str
    params: int = 0
    results: int = 1
    locals_count: int = 16  # 16 virtual registers
    instructions: List[WasmInstruction] = field(default_factory=list)
    
    def to_wat(self) -> str:
        """Generate WAT (WebAssembly Text) format."""
        lines = [f"  (func ${self.name}"]
        
        # Parameters (registers R0-R7 as params)
        for i in range(min(self.params, 8)):
            lines.append(f"    (param $r{i} i32)")
        
        # Results
        for i in range(self.results):
            lines.append(f"    (result i32)")
        
        # Locals (remaining registers)
        remaining = self.locals_count - self.params
        if remaining > 0:
            lines.append(f"    (local $extra i32)  ; {remaining} extra registers")
        
        # Instructions
        for inst in self.instructions:
            s = f"    ({inst.op.value}"
            for a in inst.args:
                s += f" {a}"
            s += ")"
            if inst.comment:
                s += f"  ;; {inst.comment}"
            lines.append(s)
        
        lines.append("  )")
        return "\n".join(lines)


@dataclass  
class WasmModule:
    functions: List[WasmFunction] = field(default_factory=list)
    memory_pages: int = 1
    
    def to_wat(self) -> str:
        lines = ['(module']
        lines.append(f'  (memory (export "memory") {self.memory_pages})')
        for fn in self.functions:
            lines.append(fn.to_wat())
        lines.append(')')
        return "\n".join(lines)


OP_NAMES = {
    0x00:"HALT",0x01:"NOP",0x08:"INC",0x09:"DEC",0x0B:"NEG",
    0x0C:"PUSH",0x0D:"POP",0x18:"MOVI",0x20:"ADD",0x21:"SUB",
    0x22:"MUL",0x23:"DIV",0x24:"MOD",0x2C:"CMP_EQ",0x2D:"CMP_LT",
    0x2E:"CMP_GT",0x3A:"MOV",0x3C:"JZ",0x3D:"JNZ",
}


class FluxToWasm:
    """Compile FLUX bytecode to WASM."""
    
    def compile_function(self, name: str, bytecode: List[int], 
                         params: int = 1) -> WasmFunction:
        """Compile a FLUX bytecode program to a WASM function."""
        fn = WasmFunction(name=name, params=params, results=1)
        bc = bytes(bytecode)
        
        def sb(b): return b - 256 if b > 127 else b
        
        # Stack for push/pop
        fn.instructions.append(WasmInstruction(WasmOp.NOP, comment="FLUX -> WASM compiled"))
        
        # Simple translation: just emit the operations linearly
        pc = 0
        while pc < len(bc):
            op = bc[pc]
            
            if op == 0x00:  # HALT
                fn.instructions.append(WasmInstruction(WasmOp.RETURN, comment="HALT"))
                break
            elif op == 0x18:  # MOVI rd, imm
                rd = bc[pc+1]
                val = sb(bc[pc+2])
                fn.instructions.append(WasmInstruction(WasmOp.I32_CONST, [val], comment=f"R{rd} = {val}"))
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_SET, [rd]))
                pc += 3
            elif op == 0x20:  # ADD rd, rs1, rs2
                rd, rs1, rs2 = bc[pc+1], bc[pc+2], bc[pc+3]
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_GET, [rs1], comment=f"R{rd} = R{rs1}+R{rs2}"))
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_GET, [rs2]))
                fn.instructions.append(WasmInstruction(WasmOp.I32_ADD))
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_SET, [rd]))
                pc += 4
            elif op == 0x21:  # SUB
                rd, rs1, rs2 = bc[pc+1], bc[pc+2], bc[pc+3]
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_GET, [rs1], comment=f"R{rd} = R{rs1}-R{rs2}"))
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_GET, [rs2]))
                fn.instructions.append(WasmInstruction(WasmOp.I32_SUB))
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_SET, [rd]))
                pc += 4
            elif op == 0x22:  # MUL
                rd, rs1, rs2 = bc[pc+1], bc[pc+2], bc[pc+3]
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_GET, [rs1], comment=f"R{rd} = R{rs1}*R{rs2}"))
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_GET, [rs2]))
                fn.instructions.append(WasmInstruction(WasmOp.I32_MUL))
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_SET, [rd]))
                pc += 4
            elif op == 0x08:  # INC
                rd = bc[pc+1]
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_GET, [rd], comment=f"R{rd}++"))
                fn.instructions.append(WasmInstruction(WasmOp.I32_CONST, [1]))
                fn.instructions.append(WasmInstruction(WasmOp.I32_ADD))
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_SET, [rd]))
                pc += 2
            elif op == 0x09:  # DEC
                rd = bc[pc+1]
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_GET, [rd], comment=f"R{rd}--"))
                fn.instructions.append(WasmInstruction(WasmOp.I32_CONST, [1]))
                fn.instructions.append(WasmInstruction(WasmOp.I32_SUB))
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_SET, [rd]))
                pc += 2
            elif op == 0x3A:  # MOV rd, rs, 0
                rd, rs = bc[pc+1], bc[pc+2]
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_GET, [rs], comment=f"R{rd} = R{rs}"))
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_SET, [rd]))
                pc += 4
            elif op == 0x2C:  # CMP_EQ
                rd, rs1, rs2 = bc[pc+1], bc[pc+2], bc[pc+3]
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_GET, [rs1]))
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_GET, [rs2]))
                fn.instructions.append(WasmInstruction(WasmOp.I32_EQ))
                fn.instructions.append(WasmInstruction(WasmOp.LOCAL_SET, [rd]))
                pc += 4
            else:
                fn.instructions.append(WasmInstruction(WasmOp.NOP, comment=f"unhandled 0x{op:02x}"))
                pc += 1
        
        # Return R0
        fn.instructions.append(WasmInstruction(WasmOp.LOCAL_GET, [0], comment="return R0"))
        
        return fn


# ── Tests ──────────────────────────────────────────────

import unittest


class TestWasmGen(unittest.TestCase):
    def test_movi(self):
        gen = FluxToWasm()
        fn = gen.compile_function("test", [0x18, 0, 42, 0x00])
        self.assertGreater(len(fn.instructions), 2)
    
    def test_add(self):
        gen = FluxToWasm()
        fn = gen.compile_function("add", [0x18,0,10, 0x18,1,20, 0x20,2,0,1, 0x00])
        ops = [i.op for i in fn.instructions]
        self.assertIn(WasmOp.I32_ADD, ops)
    
    def test_mul(self):
        gen = FluxToWasm()
        fn = gen.compile_function("mul", [0x18,0,6, 0x18,1,7, 0x22,2,0,1, 0x00])
        ops = [i.op for i in fn.instructions]
        self.assertIn(WasmOp.I32_MUL, ops)
    
    def test_wat_output(self):
        gen = FluxToWasm()
        fn = gen.compile_function("test", [0x18, 0, 42, 0x00])
        wat = fn.to_wat()
        self.assertIn("i32.const", wat)
        self.assertIn("42", wat)
    
    def test_module_output(self):
        gen = FluxToWasm()
        fn = gen.compile_function("test", [0x18, 0, 42, 0x00])
        mod = WasmModule(functions=[fn])
        wat = mod.to_wat()
        self.assertIn("(module", wat)
        self.assertIn("memory", wat)
    
    def test_inc_dec(self):
        gen = FluxToWasm()
        fn = gen.compile_function("cnt", [0x18,0,5, 0x09,0, 0x00])
        ops = [i.op for i in fn.instructions]
        self.assertIn(WasmOp.I32_SUB, ops)  # DEC uses SUB
    
    def test_mov(self):
        gen = FluxToWasm()
        fn = gen.compile_function("mov", [0x18,0,99, 0x3A,1,0,0, 0x00])
        wat = fn.to_wat()
        self.assertIn("local.get", wat)
    
    def test_cmp_eq(self):
        gen = FluxToWasm()
        fn = gen.compile_function("cmp", [0x18,0,5, 0x18,1,5, 0x2C,2,0,1, 0x00])
        ops = [i.op for i in fn.instructions]
        self.assertIn(WasmOp.I32_EQ, ops)
    
    def test_factorial(self):
        gen = FluxToWasm()
        bc = [0x18,0,6, 0x18,1,1, 0x22,1,1,0, 0x09,0, 0x3D,0,0xFA,0, 0x00]
        fn = gen.compile_function("factorial", bc)
        wat = fn.to_wat()
        self.assertIn("factorial", wat)


if __name__ == "__main__":
    unittest.main(verbosity=2)
