import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/api.ts", import.meta.url), "utf8")
    .replace('import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"', '"http://localhost:8000"');
const { outputText } = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
});
const api = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

test("A API exibe o motivo detalhado ao rejeitar uma largada", async () => {
    const previousFetch = globalThis.fetch;
    globalThis.fetch = async () => new Response(JSON.stringify({
        detail: "Com 20 carros e 60 voltas, a chuva precisa começar até a volta 21.",
    }), { status: 422, headers: { "Content-Type": "application/json" } });
    try {
        await assert.rejects(
            api.startRace({ rain_enabled: true, rain_start_lap: 30, rain_intensity: 1, incidents: [] }),
            /chuva precisa começar até a volta 21/,
        );
    } finally {
        globalThis.fetch = previousFetch;
    }
});

test("Erros de validação do FastAPI são mostrados sem o prefixo técnico", async () => {
    const previousFetch = globalThis.fetch;
    globalThis.fetch = async () => new Response(JSON.stringify({
        detail: [{ msg: "Value error, A chuva deve começar antes da última volta" }],
    }), { status: 422, headers: { "Content-Type": "application/json" } });
    try {
        await assert.rejects(
            api.startRace({ rain_enabled: true, rain_start_lap: 60, rain_intensity: 1, incidents: [] }),
            /^Error: A chuva deve começar antes da última volta$/,
        );
    } finally {
        globalThis.fetch = previousFetch;
    }
});
