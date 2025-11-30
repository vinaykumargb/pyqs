import os
import requests
import json
import random
import time

# Get Environment variables
TELEGRAM_TOKEN = os.environ.get('TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# Telegram API base URL
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Gemini API endpoint
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent"

# UPSC question patterns
QUESTION_PATTERNS = [
    "Two Statements",
    "Assertion-Reasoning",
    "Chronological/Sequential Order",
    "Match the Columns",
    "How Many Correct",
    "3/4/5 Statement Type with Multi-Option",
    "Incorrect Option",
    "Simple Term-based",
    "Descriptive but Simple",
    "Multi-Statement with Elimination",
    "Multi-Statement Logical Explanation Type"
]

def generate_mcqs(themes_text):
    """Generate 5 MCQs using Gemini AI based on given themes"""
    
    # Select 5 random patterns
    selected_patterns = random.sample(QUESTION_PATTERNS, 5)
    
    prompt = f"""You are a UPSC exam question creator. Generate exactly 5 multiple choice questions based on these themes:

{themes_text}

Each question must strictly follow one of these patterns (one question per pattern):
1. {selected_patterns[0]}
2. {selected_patterns[1]}
3. {selected_patterns[2]}
4. {selected_patterns[3]}
5. {selected_patterns[4]}

CRITICAL REQUIREMENTS:
- Each option MUST be under 90 characters (Telegram limit is 100, keeping buffer)
- Explanation MUST be under 190 characters (Telegram limit is 200, keeping buffer)
- Use concise language
- Break long statements into multiple shorter options if needed

For each question, provide:
- The question text (detailed and UPSC-style)
- Exactly 4 options (A, B, C, D), each STRICTLY under 90 characters
- The correct answer (single letter: A, B, C, or D)
- A brief explanation for the correct answer, STRICTLY under 190 characters

Format your response as a JSON array with this exact structure:
[
  {{
    "question": "Full question text here",
    "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
    "correct_answer": "A",
    "explanation": "Brief explanation here",
    "pattern": "{selected_patterns[0]}"
  }},
  ...
]

Make questions challenging and authentic to UPSC standards. Ensure all JSON is properly formatted."""

    headers = {
        "Content-Type": "application/json"
    }
    
    data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 8192
        }
    }
    
    try:
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers=headers,
            json=data,
            timeout=60
        )
        response.raise_for_status()
        
        result = response.json()
        generated_text = result['candidates'][0]['content']['parts'][0]['text']
        
        # Extract JSON from response (remove markdown code blocks if present)
        generated_text = generated_text.strip()
        if generated_text.startswith('```json'):
            generated_text = generated_text[7:]
        if generated_text.startswith('```'):
            generated_text = generated_text[3:]
        if generated_text.endswith('```'):
            generated_text = generated_text[:-3]
        generated_text = generated_text.strip()
        
        mcqs = json.loads(generated_text)
        
        # Validate and truncate options and explanations
        for mcq in mcqs:
            # Truncate options to 100 characters max
            mcq['options'] = [opt[:100] for opt in mcq['options']]
            # Truncate explanation to 200 characters max
            mcq['explanation'] = mcq['explanation'][:200] if mcq.get('explanation') else ""
            
        return mcqs
    
    except Exception as e:
        print(f"Error generating MCQs: {e}")
        return None

def send_message(chat_id, text, message_thread_id=None):
    """Send a text message to Telegram"""
    url = f"{TELEGRAM_API}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if message_thread_id:
        data["message_thread_id"] = message_thread_id
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def send_poll(chat_id, question, options, correct_option_id, explanation, message_thread_id=None):
    """Send an anonymous poll to Telegram"""
    url = f"{TELEGRAM_API}/sendPoll"
    
    # Validate and clean options
    cleaned_options = []
    for opt in options:
        # Remove any extra whitespace and truncate to 100 chars
        cleaned_opt = str(opt).strip()[:100]
        if not cleaned_opt:
            cleaned_opt = "Option"  # Fallback if empty
        cleaned_options.append(cleaned_opt)
    
    # Ensure we have exactly 4 options
    if len(cleaned_options) != 4:
        print(f"Warning: Expected 4 options, got {len(cleaned_options)}")
        return None
    
    # Validate question length (300 char limit)
    question = str(question)[:300]
    
    # Validate explanation (200 char limit)
    explanation = str(explanation).strip()[:200] if explanation else ""
    
    data = {
        "chat_id": chat_id,
        "question": question,
        "options": cleaned_options,  # Send as list, not JSON string!
        "is_anonymous": True,
        "type": "quiz",
        "correct_option_id": correct_option_id,
        "allows_multiple_answers": False
    }
    
    # Only add explanation if it's not empty
    if explanation:
        data["explanation"] = explanation
    
    if message_thread_id:
        data["message_thread_id"] = message_thread_id
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error sending poll: {e}")
        print(f"Response: {response.text if 'response' in locals() else 'No response'}")
        return None

def post_mcqs_to_telegram(chat_id, themes_text, message_thread_id=None):
    """Main function to generate and post MCQs to Telegram"""
    
    print("Generating MCQs using Gemini AI...")
    mcqs = generate_mcqs(themes_text)
    
    if not mcqs:
        print("Failed to generate MCQs")
        return False
    
    print(f"Generated {len(mcqs)} MCQs. Posting to Telegram...")
    
    # Post header message before first MCQ
    header_text = "<b>📝 Mock MCQs based on today's PYQ themes:</b>"
    send_message(chat_id, header_text, message_thread_id)
    time.sleep(1)
    
    for i, mcq in enumerate(mcqs, 1):
        try:
            # Format question with proper spacing between statements
            formatted_question = mcq['question'].replace('\n', '\n\n')
            
            # Post question text
            question_text = f"<b>Question {i}</b> ({mcq.get('pattern', 'UPSC Style')})\n\n{formatted_question}"
            send_message(chat_id, question_text, message_thread_id)
            
            time.sleep(1)  # Small delay between message and poll
            
            # Determine correct option index (A=0, B=1, C=2, D=3)
            correct_answer = mcq['correct_answer'].upper()
            correct_option_id = ord(correct_answer) - ord('A')
            
            # Validate correct_option_id
            if correct_option_id < 0 or correct_option_id > 3:
                print(f"Invalid correct answer '{correct_answer}' for MCQ {i}, defaulting to A")
                correct_option_id = 0
            
            # Post poll
            poll_question = f"Q{i}: Select the correct answer"
            result = send_poll(
                chat_id,
                poll_question,
                mcq['options'],
                correct_option_id,
                mcq.get('explanation', ''),
                message_thread_id
            )
            
            if result:
                print(f"Posted MCQ {i}/5")
            else:
                print(f"Failed to post MCQ {i}/5")
            
            time.sleep(2)  # Delay between polls
            
        except Exception as e:
            print(f"Error posting MCQ {i}: {e}")
            continue
    
    print("All MCQs posted successfully!")
    return True

# Example usage
if __name__ == "__main__":
    # Example input
    themes_input = """📌 Today's PYQ Themes:
1. The Earth and the Universe
2. Indian Map
3. Climatology
4. World Map
5. Drainage System of India"""
    
    # Replace with your chat ID and thread ID
    CHAT_ID =  -1001991761209 # Your supergroup chat ID
    THREAD_ID = None  # Your topic/thread ID (None if posting to main chat)
    
    # Validate environment variables
    if not TELEGRAM_TOKEN:
        print("Error: TOKEN environment variable not set")
        exit(1)
    
    if not GEMINI_API_KEY:
        print("Error: GEMINI_AI_API environment variable not set")
        exit(1)
    
    # Post MCQs
    post_mcqs_to_telegram(CHAT_ID, themes_input, THREAD_ID)