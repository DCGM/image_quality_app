import uvicorn
from image_rater.config import config

if __name__ == '__main__':
    uvicorn.run('image_rater.main:app', host='0.0.0.0', port=config.PORT, reload=True)
