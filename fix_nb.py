import json

with open("CerberusVision_Phase5_Colab/CerberusVision_Phase5_Qwen_QLoRA.json", "r", encoding="utf-8") as f:
    nb = json.load(f)

# Cell 2: Imports
nb["cells"][2]["source"] = [
    "import torch\n",
    "from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig\n",
    "from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training\n",
    "from datasets import load_dataset\n",
    "from trl import SFTTrainer, SFTConfig\n",
    "\n",
    "model_id = \"Qwen/Qwen2.5-7B-Instruct\"\n",
    "use_bf16 = torch.cuda.is_bf16_supported()\n",
    "compute_dtype = torch.bfloat16 if use_bf16 else torch.float16\n",
    "\n",
    "bnb_config = BitsAndBytesConfig(\n",
    "    load_in_4bit=True,\n",
    "    bnb_4bit_quant_type=\"nf4\",\n",
    "    bnb_4bit_compute_dtype=compute_dtype,\n",
    "    bnb_4bit_use_double_quant=True\n",
    ")\n",
    "\n",
    "model = AutoModelForCausalLM.from_pretrained(model_id, quantization_config=bnb_config, device_map=\"auto\")\n",
    "model = prepare_model_for_kbit_training(model)\n",
    "tokenizer = AutoTokenizer.from_pretrained(model_id)\n",
    "if tokenizer.pad_token is None:\n",
    "    tokenizer.add_special_tokens({'pad_token': '<|endoftext|>'})\n",
    "\n",
    "print(\"PAD Token ID:\", tokenizer.pad_token_id)\n",
    "print(\"EOS Token ID:\", tokenizer.eos_token_id)\n",
    "assert tokenizer.pad_token_id != tokenizer.eos_token_id\n",
    "assert tokenizer.eos_token == \"<|im_end|>\"\n"
]

# Cell 3: Data prep
nb["cells"][3]["source"] = [
    "train_dataset = load_dataset(\"json\", data_files=\"phase5_train.jsonl\", split=\"train\")\n",
    "eval_dataset = load_dataset(\"json\", data_files=\"phase5_validation.jsonl\", split=\"train\")\n",
    "\n",
    "def format_dataset(example):\n",
    "    return {\n",
    "        \"prompt\": [\n",
    "            {\"role\": \"system\", \"content\": \"Extract shipping instruction data from OCR text as JSON.\"},\n",
    "            {\"role\": \"user\", \"content\": str(example['input'])}\n",
    "        ],\n",
    "        \"completion\": [\n",
    "            {\"role\": \"assistant\", \"content\": str(example['output'])}\n",
    "        ]\n",
    "    }\n",
    "\n",
    "train_dataset = train_dataset.map(format_dataset, remove_columns=train_dataset.column_names)\n",
    "eval_dataset = eval_dataset.map(format_dataset, remove_columns=eval_dataset.column_names)\n",
    "print(f\"Train size: {len(train_dataset)}, Eval size: {len(eval_dataset)}\")\n"
]

# Remove cell 4 (dry run)
nb["cells"] = [c for c in nb["cells"] if c.get("metadata", {}).get("id") != "dry_run_sanity_check"]

# Fix training cell
for c in nb["cells"]:
    if c.get("metadata", {}).get("id") == "training":
        new_source = []
        for line in c["source"]:
            if "dataset_text_field" in line:
                continue
            if "data_collator" in line:
                continue
            new_source.append(line)
            if "max_length=2048" in line:
                new_source.append("    completion_only_loss=True,\n")
                new_source.append("    eos_token=\"<|im_end|>\",\n")
        c["source"] = new_source

with open("CerberusVision_Phase5_Colab/CerberusVision_Phase5_Qwen_QLoRA.json", "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=2, ensure_ascii=False)
