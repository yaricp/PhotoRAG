import tempfile
import os
from src.watcher import generate_file_hash, process_new_file

def test_generate_file_hash():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test data")
        temp_name = f.name
    
    file_hash = generate_file_hash(temp_name)
    os.remove(temp_name)
    assert file_hash == "916f0027a575074ce72a331777c3478d6513f786a591bd892da1a577bf2335f9"
