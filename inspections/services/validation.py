from PIL import Image, UnidentifiedImageError


MAX_FILE_SIZE = 5 * 1024 * 1024
MIN_DIMENSION = 64
MAX_DIMENSION = 4096
ALLOWED_FORMATS = {"JPEG", "PNG"}


def validate_image(uploaded_file):
    """Validate image content and dimensions before it reaches inference."""
    if uploaded_file is None:
        return "No image file was submitted."
    if uploaded_file.size > MAX_FILE_SIZE:
        return "Uploaded file exceeds the 5 MiB limit."
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            image.verify()
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            if image.format not in ALLOWED_FORMATS:
                return "Unsupported file format. Only JPEG and PNG are allowed."
            width, height = image.size
    except (UnidentifiedImageError, OSError, SyntaxError):
        return "The uploaded file is not a valid image or is corrupted."
    finally:
        uploaded_file.seek(0)
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        return "Image dimensions are below the minimum requirement of 64 x 64 pixels."
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        return "Image dimensions exceed the maximum requirement of 4096 x 4096 pixels."
    return None
