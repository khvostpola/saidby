# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    system: str
    user: str
    kind_person: str
    kind_term: str
    usually_written: str
    confused_with: str
    context: str
    directory_title: str


PROMPTS: dict[str, PromptTemplate] = {
    "en": PromptTemplate(
        system=(
            "You fix automatic transcriptions. You may only propose replacing one word, or a group "
            "of up to three consecutive words, with a term from the directory, when the context "
            "clearly shows the speaker said that term and the recognizer misspelled it. Do not "
            "fix spelling, grammar, punctuation or any other word. Do not propose terms that "
            "are already spelled correctly. If nothing needs fixing, return an empty list."
        ),
        user="Transcript with the index of each word:\n",
        kind_person="person",
        kind_term="term",
        usually_written="often comes out as",
        confused_with="gets confused with the real word",
        context="context",
        directory_title="Directory",
    ),
    "es": PromptTemplate(
        system=(
            "Corriges transcripciones automáticas. Solo puedes proponer reemplazar una palabra "
            "o un grupo de hasta tres palabras consecutivas por un término del directorio, "
            "cuando el "
            "contexto muestre con claridad que la persona dijo ese término y el reconocedor lo "
            "escribió mal. No corrijas ortografía, gramática, puntuación ni ninguna otra palabra. "
            "No propongas términos que ya están bien escritos. Si no hay nada que corregir, "
            "devuelve una lista vacía."
        ),
        user="Transcripción con el índice de cada palabra:\n",
        kind_person="persona",
        kind_term="término",
        usually_written="suele salir como",
        confused_with="se confunde con la palabra real",
        context="contexto",
        directory_title="Directorio",
    ),
    "pt": PromptTemplate(
        system=(
            "Você corrige transcrições automáticas. Só pode propor substituir uma palavra, ou um "
            "grupo de até três palavras consecutivas, por um termo do diretório, quando o contexto "
            "mostrar claramente que a pessoa disse esse termo e o reconhecedor o escreveu errado. "
            "Não corrija ortografia, gramática, pontuação nem qualquer outra palavra. Não proponha "
            "termos que já estão escritos corretamente. Se não houver nada a corrigir, devolva uma "
            "lista vazia."
        ),
        user="Transcrição com o índice de cada palavra:\n",
        kind_person="pessoa",
        kind_term="termo",
        usually_written="costuma sair como",
        confused_with="é confundido com a palavra real",
        context="contexto",
        directory_title="Diretório",
    ),
}
PROMPT_VERSION = 1


def template_for(language: str | None) -> PromptTemplate:
    return PROMPTS.get((language or "en").split("-")[0].lower(), PROMPTS["en"])
