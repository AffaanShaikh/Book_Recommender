import os
import uvicorn
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer


# Put your Google Books API key in 'Google_Books_API_Key' in .env file
load_dotenv() 
api_key_ = os.getenv('Google_Books_API_Key')

app = FastAPI()


# LLM model for recommendation
model_name = "distilgpt2"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)


class RequestedBook(BaseModel):
    """
    Defines a Pydantic model for the book request, ensuring that incoming data has the required structure.
    """
    genre: str
    preferences: str

def fetch_books_by_genre(genre, max_results=None, api_key=None):
    """
    Fetches books from the Google Books API based on the specified genre.
    """
    url = f"https://www.googleapis.com/books/v1/volumes?q=subject:{genre}&maxResults={max_results}&key={api_key}"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception("Error fetching books from API.")
    books = response.json().get('items', [])
    return books

def top10_books(books):
    """
    Sorts books based on their average rating and rating count, then returns the top 10.
    """
    sorted_books = sorted(books, key=lambda x: (x['volumeInfo'].get('averageRating', 0), x['volumeInfo'].get('ratingsCount', 0)), reverse=True)
    return sorted_books[:10]

def recommend(top_10_books, preferences):
    """
    Recommend a book from the top 10 books based on user preferences using the language model.
    """
    prompt = f"User preferences: {preferences}. Recommend a book from the following list:\n"
    for i, book in enumerate(top_10_books, 1):
        prompt += f"{i}. {book['volumeInfo']['title']} by {', '.join(book['volumeInfo'].get('authors', []))}\n"
    prompt += "\nRecommendation:"

    inputs = tokenizer.encode(prompt, return_tensors="pt")
    outputs = model.generate(inputs, max_length=300, num_return_sequences=1)
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)

    recommended_title = response.split("Recommendation:")[1].split("\n")[0].strip()

    for book in top_10_books:
        if recommended_title.lower() in book['volumeInfo']['title'].lower():
            return book

    return top_10_books[0]



@app.get("/", response_class=HTMLResponse)
async def read_home():
    html_content = """
    <html>
        <head>
            <title>Book Recommendation</title>
        </head>
        <body>
            <h1>Book Recommendation Service</h1>
            <form action="/submit" method="post">
                <label for="genre">Genre:</label>
                <input type="text" id="genre" name="genre"><br><br>
                <label for="preferences">Preferences:</label>
                <input type="text" id="preferences" name="preferences"><br><br>
                <input type="submit" value="Get Recommendation">
            </form>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/recommend")
async def recommend_book_endpoint(genre: str = Form(...), preferences: str = Form(...)):
    try:
        request = RequestedBook(genre=genre, preferences=preferences)
        books = fetch_books_by_genre(request.genre, max_results=40, api_key=api_key_)
        top_10_books = top10_books(books)
        recommended_book = recommend(top_10_books, request.preferences)
        response = {
            "recommended_book": {
                "title": recommended_book['volumeInfo']['title'],
                "authors": recommended_book['volumeInfo'].get('authors', []),
                "publishedDate": recommended_book['volumeInfo'].get('publishedDate', 'N/A'),
                "averageRating": recommended_book['volumeInfo'].get('averageRating', 'N/A'),
                "description": recommended_book['volumeInfo'].get('description', 'No description available')
            },
            "thank_you_message": "Thank you for using this book recommendation service! Read well!"
        }
    except Exception as e:
        response = {
            "error": str(e),
            "message": "An error occurred while processing your request."
        }
    return response

@app.post("/submit")
async def submit_form(genre: str = Form(...), preferences: str = Form(...)):
    response = await recommend_book_endpoint(genre, preferences)
    if "error" in response:
        html_content = f"""
        <html>
            <body>
                <h1>Error</h1>
                <p>{response['message']}</p>
                <p>{response['error']}</p>
            </body>
        </html>
        """
    else:
        recommended_book = response['recommended_book']
        html_content = f"""
        <html>
            <body>
                <h1>Book Recommendation</h1>
                <p><strong>Title:</strong> {recommended_book['title']}</p>
                <p><strong>Authors:</strong> {', '.join(recommended_book['authors'])}</p>
                <p><strong>Published Date:</strong> {recommended_book['publishedDate']}</p>
                <p><strong>Average Rating:</strong> {recommended_book['averageRating']}</p>
                <p><strong>Description:</strong> {recommended_book['description']}</p>
                <p>{response['thank_you_message']}</p>
            </body>
        </html>
        """
    return HTMLResponse(content=html_content)



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
