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

# Gemini API endpoint - Using Gemini 1.5 Flash (Higher free tier limits)
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# Rate limiting
LAST_API_CALL_TIME = 0
MIN_TIME_BETWEEN_CALLS = 2  # seconds between API calls

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

def generate_mcqs(themes_text, max_retries=5):
    """Generate 5 MCQs using Gemini AI based on given themes"""
    global LAST_API_CALL_TIME
    
    # Enforce rate limiting
    time_since_last_call = time.time() - LAST_API_CALL_TIME
    if time_since_last_call < MIN_TIME_BETWEEN_CALLS:
        wait_time = MIN_TIME_BETWEEN_CALLS - time_since_last_call
        print(f"⏱️  Rate limiting: waiting {wait_time:.1f} seconds...")
        time.sleep(wait_time)
    
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
    
    for attempt in range(max_retries):
        try:
            print(f"🔄 Attempt {attempt + 1}/{max_retries}: Calling Gemini 1.5 Flash API...")
            
            response = requests.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                headers=headers,
                json=data,
                timeout=60
            )
            response.raise_for_status()
            
            LAST_API_CALL_TIME = time.time()  # Update successful call time
            
            result = response.json()
            
            # Check if response has the expected structure
            if 'candidates' not in result or len(result['candidates']) == 0:
                print(f"⚠️  Unexpected API response structure")
                print(f"Response: {json.dumps(result, indent=2)}")
                return None
            
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
            
            # Parse JSON
            mcqs = json.loads(generated_text)
            
            # Validate and truncate options and explanations
            for mcq in mcqs:
                # Truncate options to 100 characters max
                mcq['options'] = [opt[:100] for opt in mcq['options']]
                # Truncate explanation to 200 characters max
                mcq['explanation'] = mcq['explanation'][:200] if mcq.get('explanation') else ""
            
            print(f"✅ Successfully generated {len(mcqs)} MCQs")
            return mcqs
        
        except requests.exceptions.HTTPError as e:
            error_data = None
            try:
                error_data = e.response.json()
            except:
                pass
            
            if e.response.status_code == 429:
                # Check if it's a quota exhaustion or rate limit
                if error_data and 'error' in error_data:
                    error_msg = error_data['error'].get('message', '')
                    
                    # Check for daily quota exhaustion
                    if 'quota exceeded' in error_msg.lower() and 'perday' in error_msg.lower():
                        print(f"❌ DAILY QUOTA EXHAUSTED")
                        print(f"💡 Your daily quota for this model has been reached.")
                        print(f"📊 Check usage at: https://ai.dev/usage?tab=rate-limit")
                        print(f"⏰ Wait until tomorrow or consider upgrading your plan")
                        return None
                    
                    # Check for retry delay
                    if 'retry' in error_msg.lower():
                        import re
                        match = re.search(r'retry in (\d+\.?\d*)s', error_msg)
                        if match:
                            retry_delay = float(match.group(1))
                            print(f"⏳ API suggests waiting {retry_delay:.1f} seconds...")
                            time.sleep(retry_delay + 1)
                            continue
                
                # Standard exponential backoff: 5, 10, 20, 40, 80 seconds
                wait_time = (2 ** attempt) * 5
                print(f"⚠️  Rate limit hit (429). Attempt {attempt + 1}/{max_retries}")
                print(f"⏳ Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                
                if attempt == max_retries - 1:
                    print(f"❌ Max retries reached.")
                    print(f"💡 Tips:")
                    print(f"   - Wait a few minutes and try again")
                    print(f"   - Check your quota at: https://ai.dev/usage")
                    print(f"   - Consider using a different API key")
                    return None
            
            elif e.response.status_code == 503:
                wait_time = (attempt + 1) * 10
                print(f"⚠️  Service unavailable (503). Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                
                if attempt == max_retries - 1:
                    print(f"❌ Service unavailable after {max_retries} attempts.")
                    return None
            
            else:
                print(f"❌ HTTP Error {e.response.status_code}: {e}")
                if error_data:
                    print(f"Error details: {json.dumps(error_data, indent=2)}")
                else:
                    print(f"Response text: {e.response.text[:500]}")
                return None
        
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {e}")
            print(f"Response text: {generated_text[:500]}...")
            
            # Try one more time on JSON error
            if attempt < max_retries - 1:
                print(f"🔄 Retrying due to JSON parse error...")
                time.sleep(5)
                continue
            return None
        
        except KeyError as e:
            print(f"❌ Missing expected key in response: {e}")
            print(f"Response structure: {json.dumps(result, indent=2)[:500]}...")
            return None
        
        except Exception as e:
            print(f"❌ Unexpected error: {type(e).__name__}: {e}")
            if attempt < max_retries - 1:
                print(f"🔄 Retrying...")
                time.sleep(5)
                continue
            return None
    
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
        print(f"❌ Error sending message: {e}")
        return None

def send_poll(chat_id, question, options, correct_option_id, explanation, message_thread_id=None):
    """Send an anonymous quiz poll to Telegram"""
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
        print(f"⚠️  Warning: Expected 4 options, got {len(cleaned_options)}")
        return None
    
    # Validate question length (300 char limit)
    question = str(question)[:300]
    
    # Validate explanation (200 char limit)
    explanation = str(explanation).strip()[:200] if explanation else ""
    
    data = {
        "chat_id": chat_id,
        "question": question,
        "options": cleaned_options,
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
        print(f"❌ Error sending poll: {e}")
        try:
            error_detail = response.json()
            print(f"Error details: {json.dumps(error_detail, indent=2)}")
        except:
            print(f"Response: {response.text if 'response' in locals() else 'No response'}")
        return None

def post_mcqs_to_telegram(chat_id, themes_text, message_thread_id=None):
    """Main function to generate and post MCQs to Telegram"""
    
    print("=" * 60)
    print("🚀 Starting MCQ Generation Process")
    print("=" * 60)
    print(f"📝 Themes:\n{themes_text}\n")
    
    print("🤖 Generating MCQs using Gemini 1.5 Flash...")
    mcqs = generate_mcqs(themes_text)
    
    if not mcqs:
        print("❌ Failed to generate MCQs")
        return False
    
    print(f"\n✅ Generated {len(mcqs)} MCQs. Posting to Telegram...")
    print("=" * 60)
    
    # Post header message before first MCQ
    header_text = "<b>📝 Mock MCQs based on today's PYQ themes:</b>"
    send_message(chat_id, header_text, message_thread_id)
    time.sleep(1)
    
    successful_posts = 0
    
    for i, mcq in enumerate(mcqs, 1):
        try:
            print(f"\n📤 Posting MCQ {i}/5...")
            
            # Format question with proper spacing between statements
            formatted_question = mcq['question'].replace('\n', '\n\n')
            
            # Post question text
            question_text = f"<b>Question {i}</b> ({mcq.get('pattern', 'UPSC Style')})\n\n{formatted_question}"
            msg_result = send_message(chat_id, question_text, message_thread_id)
            
            if not msg_result:
                print(f"⚠️  Failed to send question text for MCQ {i}")
                continue
            
            time.sleep(1)  # Small delay between message and poll
            
            # Determine correct option index (A=0, B=1, C=2, D=3)
            correct_answer = mcq['correct_answer'].upper()
            correct_option_id = ord(correct_answer) - ord('A')
            
            # Validate correct_option_id
            if correct_option_id < 0 or correct_option_id > 3:
                print(f"⚠️  Invalid correct answer '{correct_answer}' for MCQ {i}, defaulting to A")
                correct_option_id = 0
            
            # Post poll
            poll_question = f"Q{i}: Select the correct answer"
            poll_result = send_poll(
                chat_id,
                poll_question,
                mcq['options'],
                correct_option_id,
                mcq.get('explanation', ''),
                message_thread_id
            )
            
            if poll_result:
                print(f"✅ Successfully posted MCQ {i}/5")
                successful_posts += 1
            else:
                print(f"❌ Failed to post poll for MCQ {i}/5")
            
            time.sleep(2)  # Delay between polls
            
        except Exception as e:
            print(f"❌ Error posting MCQ {i}: {type(e).__name__}: {e}")
            continue
    
    print("\n" + "=" * 60)
    print(f"✅ Process Complete: {successful_posts}/{len(mcqs)} MCQs posted successfully!")
    print("=" * 60)
    
    return successful_posts == len(mcqs)

# Example usage
if __name__ == "__main__":
    print("=" * 60)
    print("🎯 UPSC MCQ Generator with Gemini 1.5 Flash")
    print("=" * 60)
    
    # Validate environment variables
    if not TELEGRAM_TOKEN:
        print("❌ Error: TOKEN environment variable not set")
        print("💡 Set it with: export TOKEN='your_telegram_bot_token'")
        exit(1)
    
    if not GEMINI_API_KEY:
        print("❌ Error: GEMINI_API_KEY environment variable not set")
        print("💡 Set it with: export GEMINI_API_KEY='your_gemini_api_key'")
        print("💡 Get your key at: https://aistudio.google.com/app/apikey")
        exit(1)
    
    print("✅ Environment variables validated")
    print(f"📡 Using model: gemini-2.5-flash")
    
    # Example input
    themes_input = """📌 Today's PYQ Themes:
1. Finance Commission, Black Money, Subsidies
2. Sectors of Economy - Agriculture
3. Bank Classification
4. Sectors of Economy - Agriculture
5. WTO, IMF & Other Intl. Orgs & Agreements"""
    
    # Replace with your chat ID and thread ID
    CHAT_ID = -1001991761209  # Your supergroup chat ID
    THREAD_ID = None  # Your topic/thread ID (None if posting to main chat)
    
    # Post MCQs
    success = post_mcqs_to_telegram(CHAT_ID, themes_input, THREAD_ID)
    
    if success:
        print("\n🎉 All MCQs posted successfully!")
    else:
        print("\n⚠️  Some MCQs failed to post. Check the logs above.")