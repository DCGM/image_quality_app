import uvicorn
from text_classifier.config import config

if __name__ == '__main__':
    uvicorn.run('text_classifier.main:app', host='0.0.0.0', port=config.PORT, reload=True)
