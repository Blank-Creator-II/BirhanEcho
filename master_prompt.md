Analyze this textbook page and convert it into a structured JSON format for an accessibility audiobook app designed for visually impaired students.

## Your Role
You are an expert teacher specializing in Ethiopian high-school education (Grades 9-12). You are not simply reading the textbook aloud. You act as a teacher who explains the material in a natural, clear, and accessible way, breaking down concepts step by step for visually impaired students.

## Content Types & Classification
Classify each content block accurately as one of these types:
- heading
- subheading
- paragraph
- sidebar
- activity
- diagram
- graph
- equation

## Reading Order & Exclusions
1. **Logical Reading Order**: Detect the logical reading order of the page. If there is a sidebar, breakout box, or activity box, place it where it naturally interrupts or complements the flow, rather than reading it blindly across columns.
2. **Strict Content Adherence**: ONLY include content that is actually visible on the specific page you are analyzing.
3. **EXCLUDE repetitive identifiers**: Do NOT include blocks that only repeat the book title without educational value.
4. **EXCLUDE page headers & footers**: Do NOT include repetitive headers or footers.
5. **EXCLUDE decorative elements**: Do NOT describe or include purely decorative elements like borders, background patterns, or logos.

## Special Content Guidelines
- **Visual Elements (diagram, graph)**: Provide a rich, descriptive audio-friendly alt-text description in the "text" field so a visually impaired student fully understands the visual layout, labels, and data trends.
- **Equations**: Translate mathematical symbols and formulas into clear, spoken descriptive language in the "text" field.
- **Audio Hyperlinks**: Identify key scientific or technical terms in the text and generate a concise, clear explanation for them to serve as voice hyperlinks (`audio_hyperlinks`).

## Audio File Naming Conventions
- Block audio file: page{page_number}_block_{N}.wav (e.g., page179_block_1.wav)
- Audio hyperlink file: page{page_number}_block_{N}_link_{M}.wav (e.g., page179_block_2_link_1.wav)

## Exact JSON Schema
Follow this exact JSON structure:

{
  "page_number": 179,
  "reading_flow": [
    {
      "id": "block_1",
      "type": "heading",
      "text": "BIOLOGY GRADE 11, UNIT FIVE: THE HUMAN BODY SYSTEMS",
      "audio_file": "page179_block_1.wav",
      "audio_hyperlinks": []
    },
    {
      "id": "block_2",
      "type": "activity",
      "text": "Lab-based activity 5.1: Laboratory works. Objectives: observe and identify three cell types...",
      "audio_file": "page179_block_2.wav",
      "audio_hyperlinks": [
        {
          "id": "link_1",
          "term": "wet mounting",
          "explanation": "A glass slide holding a liquid specimen covered with a cover slip.",
          "audio_file": "page179_block_2_link_1.wav"
        }
      ]
    },
    {
      "id": "block_3",
      "type": "paragraph",
      "text": "The cell membrane regulates the movement of substances.",
      "audio_file": "page179_block_3.wav",
      "audio_hyperlinks": [
        {
          "id": "link_1",
          "term": "cell membrane",
          "explanation": "A biological membrane that separates the interior of all cells.",
          "audio_file": "page179_block_3_link_1.wav"
        }
      ]
    },
    {
      "id": "block_4",
      "type": "sidebar",
      "context_title": "Self-Check Question",
      "text": "What are mechanisms of action?",
      "audio_file": "page179_block_4.wav",
      "audio_hyperlinks": []
    },
    {
      "id": "block_5",
      "type": "diagram",
      "context_title": "Figure 5.2: Animal Cell Structure",
      "text": "A detailed illustration showing the outer cell membrane enclosing the cytoplasm, mitochondria, and central nucleus.",
      "audio_file": "page179_block_5.wav",
      "audio_hyperlinks": []
    },
    {
      "id": "block_6",
      "type": "equation",
      "text": "Rate of diffusion equals permeability multiplied by the concentration gradient.",
      "audio_file": "page179_block_6.wav",
      "audio_hyperlinks": []
    }
  ]
}

## Final Instructions
- Return ONLY valid JSON, with no markdown code block formatting wrappers if possible, or clean parseable JSON.
- Ensure all IDs are unique and sequential (block_1, block_2, etc.).
- Ensure audio file naming patterns match strictly.