# Flask to mGBA LUA

Javascript -> HTTP POST -> Flask -> TCP Socket -> mGBA Lua

## Linux

### First time setup Linux

```
python -m venv env
pip install -r requirements.txt
```

### Activate environment

```
source env/bin/activate
```

### Run App

`python controller.py`

## Windows

god knows, my windows python install is so cooked

## TODO

* ~~get app working with linux uinput~~
* ~~get app working with mgba lua and sockets~~ (much better idea)
* ~~only send valid keys in frontend js~~
* ~~visual feedback in front end~~
* ~~connection status in frontend~~
* ~~clean up lua~~
* ~~separate out vars nicely lua~~
* arguments for host and port
* ~~separate out vars nicely python~~
* ~~up and down press events~~
* connection status for emulator and POST in frontend
* ~~buffer (if I cant implement up and down presses)~~
* ~~use dictionaries?~~
* ~~add comments (cringe)~~
* create two bytes representing the input in python, send w/socket, use setKeys() with it in lua
* add more comments (cringe)

