import cloudinary
import cloudinary.uploader
import os

# Настраиваем Cloudinary
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

async def upload_photo(file_path: str) -> str:
    """Загрузить фото в Cloudinary и вернуть URL"""
    try:
        result = cloudinary.uploader.upload(
            file_path,
            folder="cloudshop",
            resource_type="image"
        )
        return result['secure_url']
    except Exception as e:
        print(f"Ошибка загрузки в Cloudinary: {e}")
        return ""

async def delete_photo(image_url: str):
    """Удалить фото из Cloudinary"""
    if not image_url or "cloudinary.com" not in image_url:
        return
    
    try:
        # Извлекаем public_id из URL
        parts = image_url.split("/")
        upload_idx = parts.index("upload")
        path_with_version = "/".join(parts[upload_idx + 1:])
        # Убираем версию (v123/)
        if path_with_version.startswith("v"):
            path_with_version = "/".join(path_with_version.split("/")[1:])
        # Убираем расширение
        public_id = path_with_version.rsplit(".", 1)[0]
        
        cloudinary.uploader.destroy(public_id)
        print(f"Фото удалено из Cloudinary: {public_id}")
    except Exception as e:
        print(f"Ошибка удаления из Cloudinary: {e}")
