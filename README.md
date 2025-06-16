# MiM - Custom Merchandise Creator

A conversational interface for creating custom merchandise using Printify API and OpenAI. Users can request products like "I want a red hat with my logo" and the app will create mockups using AI.

## Features

- 🎨 **Conversational Interface**: Request products naturally ("make me a blue t-shirt")
- 🎯 **Smart Product Matching**: AI-powered product search and selection
- 🌈 **Color Selection**: Support for various colors with fuzzy matching
- 📱 **Logo Upload**: Upload and position logos on products
- 🖼️ **Mockup Generation**: Automatic product mockup creation
- 🔄 **Real-time Updates**: Live chat interface with product previews

## Live Demo

🚀 **[Try MiM Live on Vercel](https://your-app-name.vercel.app)**

## Local Development

### Prerequisites

- Python 3.8+
- OpenAI API Key
- Printify API Token

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/nathan-eagle/MiM.git
   cd MiM
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your API keys
   ```

4. **Run the application**
   ```bash
   python flaskApp/app.py
   ```

5. **Open your browser**
   ```
   http://localhost:5000
   ```

## Deployment on Vercel

### One-Click Deploy

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/nathan-eagle/MiM)

### Manual Deployment

1. **Fork this repository**

2. **Connect to Vercel**
   - Go to [vercel.com](https://vercel.com)
   - Import your forked repository

3. **Set Environment Variables**
   In your Vercel dashboard, add these environment variables:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `PRINTIFY_API_TOKEN`: Your Printify API token

4. **Deploy**
   - Vercel will automatically deploy your app
   - Your app will be available at `https://your-app-name.vercel.app`

## API Keys Setup

### OpenAI API Key
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key to your environment variables

### Printify API Token
1. Go to [Printify API Settings](https://printify.com/app/account/api)
2. Create a new API token
3. Copy the token to your environment variables

## How It Works

1. **User Input**: Users type natural language requests like "red hat" or "blue t-shirt"
2. **AI Processing**: OpenAI analyzes the request to extract product type and color
3. **Product Search**: The app searches Printify's catalog for matching products
4. **Color Matching**: Fuzzy matching finds the closest available colors
5. **Mockup Generation**: Creates product mockups with uploaded logos
6. **Real-time Display**: Shows the result in a chat-like interface

## Supported Products

- T-Shirts (various styles)
- Hats (Dad hats, Trucker caps, Baseball caps)
- Hoodies and Sweatshirts
- Tank Tops
- And many more from Printify's catalog

## Color Support

The app supports intelligent color matching:
- **Exact matches**: "red" → "Red"
- **Fuzzy matches**: "blue" → "Light Blue", "Navy", "Royal"
- **Fallback**: Lists available colors when requested color isn't found

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues or questions:
- Open an issue on GitHub
- Check the logs in Vercel dashboard for debugging 