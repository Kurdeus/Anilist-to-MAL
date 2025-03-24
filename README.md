# Anilist-to-MAL

A simple desktop application to export your [Anilist.co](https://anilist.co/) anime and manga lists to MyAnimeList XML format.

## Features

- Export User Anime/Manga list to [MyAnimeList](https://myanimelist.net/) XML export file (Can be imported to [MyAnimeList](https://myanimelist.net/import.php)).
- User-friendly GUI interface
- Save your configuration for future use
- Select your preferred browser for authentication
- Progress tracking during export

## Requirements
- Python 3.6+
- 2GB RAM, or higher.
- Stable internet connection.



# Setup:
1. Download the latest version of the application from the [Releases](https://github.com/Kurdeus/Anilist-to-MAL/releases) page.
2. Go to Anilist [**Settings** -> **Developer**](https://anilist.co/settings/developer), and click **Create client**.
  - Type whatever in **Name** field, and use ``http://127.0.0.1:8000/callback`` as **Redirect URL**.
  - Get information from created client and input them in **config.json** (Automatically created if not existing, you need to input the credentials).
  - File must contain these lines. *Replace lines with appropriate values*:
```json
{
    "username": "Username",
    "aniclient": "ID",
    "anisecret": "Secret",
    "redirectUrl": "http://127.0.0.1:8000/callback"
}
```



## How to Import to MyAnimeList

1. Go to [MyAnimeList Import](https://myanimelist.net/import.php)
2. Select the exported XML file
3. Follow the import instructions on MyAnimeList

## License

This project is licensed under the MIT License - see the LICENSE file for details.