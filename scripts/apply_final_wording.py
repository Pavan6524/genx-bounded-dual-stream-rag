import json

def apply_final_wording_corrections():
    with open('workflows/ingestion_firewall_runtime_test.json', 'r', encoding='utf-8') as f:
        wf = json.load(f)

    target_node = None
    for n in wf['nodes']:
        if n['name'] == 'Ollama Framework Extractor':
            target_node = n
            break

    assert target_node is not None, "Node 'Ollama Framework Extractor' not found!"

    refined_json_body = (
        "={\n"
        "  \"model\": \"{{ $env.OLLAMA_LLM_MODEL || 'llama3.2:1b' }}\",\n"
        "  \"prompt\": \"You are a coaching knowledge extractor. Extract only explicitly discussed coaching frameworks and diagnostic rules from this transcript.\\n\\n"
        "Rules:\\n"
        "1. Framework Names: When Dr. Sara Hegy explicitly names a framework (e.g. 'Completion with Integrity', 'Table and Shoulder Test'), retain that exact name. Unnamed concepts may use concise descriptive labels, but never invent formal framework names or split one coherent framework into fragmented concepts.\\n"
        "2. Definition: Explain what the framework is conceptually. If not explicitly defined, return an empty string \\\"\\\". Never use conversational instructions or closing remarks as definitions.\\n"
        "3. Core Mechanism: Detail the concrete diagnostic rule or operational mechanism. Extract decision logic only when explicitly supported by the current transcript. The Table and Shoulder Test example must not introduce unsupported concepts into unrelated sessions. For Completion with Integrity, preserve that surveillance drops as clarity increases. Never use generic directives like \\\"Run the test\\\".\\n"
        "4. Application: Describe the client-specific leadership application directly supported by the transcript. If unsupported, return an empty string \\\"\\\". Never use generic sign-offs or \\\"report back\\\" as application.\\n"
        "5. Source Timestamps: Every source timestamp must exactly match a timestamp present in the original transcript. Never invent timestamps.\\n\\n"
        "Transcript:\\n\" + $('Validate Classification').item.json.dialogue_text + \"\\n\\n"
        "Return JSON with this exact schema:\\n"
        "{\\n"
        "  \\\"frameworks\\\": [\\n"
        "    {\\n"
        "      \\\"name\\\": \\\"Exact Framework Name\\\",\\n"
        "      \\\"definition\\\": \\\"Definition or empty string\\\",\\n"
        "      \\\"core_mechanism\\\": \\\"Exact diagnostic rule or mechanism\\\",\\n"
        "      \\\"application\\\": \\\"Client application or empty string\\\",\\n"
        "      \\\"source_timestamps\\\": [\\\"00:00:45\\\"]\\n"
        "    }\\n"
        "  ]\\n"
        "}\",\n"
        "  \"format\": \"json\",\n"
        "  \"stream\": false,\n"
        "  \"options\": {\n"
        "    \"temperature\": 0.0\n"
        "  }\n"
        "}"
    )

    target_node['parameters']['jsonBody'] = refined_json_body

    with open('workflows/ingestion_firewall_runtime_test.json', 'w', encoding='utf-8') as f:
        json.dump(wf, f, indent=2)

    print("Successfully updated wording corrections in workflows/ingestion_firewall_runtime_test.json")

if __name__ == '__main__':
    apply_final_wording_corrections()
