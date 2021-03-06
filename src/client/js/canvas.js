//var global = require('./global');

class Canvas {
    constructor() {
        this.directionLock = false;
        this.target = global.target;
        this.reenviar = true;
        this.socket = global.socket;
        this.directions = [];
        const self = this;

        this.cv = document.getElementById('cvs');
        this.cv.width = global.screenWidth;
        this.cv.height = global.screenHeight;
        this.cv.addEventListener('mousemove', this.gameInput, false);
        this.cv.addEventListener('mouseout', this.outOfBounds, false);
        this.cv.addEventListener('keypress', this.keyInput, false);
        this.cv.addEventListener('keyup', function(event) {
            self.reenviar = true;
            self.directionUp(event);
        }, false);
        this.cv.addEventListener('keydown', this.directionDown, false);
        this.cv.addEventListener('touchstart', this.touchInput, false);
        this.cv.addEventListener('touchmove', this.touchInput, false);
        this.cv.addEventListener('click', function(event){
            this.parent.socket.emit('fire_gun');
        }, false)
        this.cv.parent = self;
        global.canvas = this;

        setInterval(()=>{
            for (let i =0; i < self.directions.length; i++){
                if (self.directions[i] === global.KEY_A){ // KEY_A is used to move left, since KEY_LEFT is spin turret
                    self.socket.emit('strafe_left');
                } else if (self.directions[i] === global.KEY_D){ // KEY_D is used to move left, since KEY_RIGHT is spin turret
                    self.socket.emit('strafe_right');
                } else if (self.directions[i]===global.KEY_LEFT){
                    self.socket.emit('angle_left');
                } else if (self.directions[i]===global.KEY_RIGHT){
                    self.socket.emit('angle_right');
                } else if (self.directions[i]===global.KEY_UP){
                    self.socket.emit('power_up');
                } else if (self.directions[i]===global.KEY_DOWN){
                    self.socket.emit('power_down');
                }
            }}, 10)
    }

    // Function called when a key is pressed, will change direction if arrow key.
    directionDown(event) {
    	var key = event.which || event.keyCode;
        var self = this.parent; // have to do this so we are not using the cv object
    	if (self.directional(key)) {
    		self.directionLock = true;
    		if (self.newDirection(key, self.directions, true)) {
    			self.updateTarget(self.directions);
    			self.socket.emit('0', self.target);
    		}
    	}
    }

    // Function called when a key is lifted, will change direction if arrow key.
    directionUp(event) {
    	var key = event.which || event.keyCode;
    	if (this.directional(key)) { // this == the actual class
    		if (this.newDirection(key, this.directions, false)) {
    			this.updateTarget(this.directions);
    			if (this.directions.length === 0) this.directionLock = false;
    			this.socket.emit('0', this.target);
    		}
    	}
    }

    // Updates the direction array including information about the new direction.
    newDirection(direction, list, isAddition) {
    	var result = false;
    	var found = false;
    	for (var i = 0, len = list.length; i < len; i++) {
    		if (list[i] === direction) {
    			found = true;
    			if (!isAddition) {
    				result = true;
    				// Removes the direction.
    				list.splice(i, 1);
    			}
    			break;
    		}
    	}
    	// Adds the direction.
    	if (isAddition && found === false) {
    		result = true;
    		list.push(direction);
    	}

    	return result;
    }

    // Updates the target according to the directions in the directions array.
    updateTarget(list) {
    	this.target = { x : 0, y: 0 };
    	var directionHorizontal = 0;
    	var directionVertical = 0;
    	// for (var i = 0, len = list.length; i < len; i++) {
    	// 	if (directionHorizontal === 0) {
    	// 		if (list[i] === global.KEY_LEFT) directionHorizontal -= Number.MAX_VALUE;
    	// 		else if (list[i] === global.KEY_RIGHT) directionHorizontal += Number.MAX_VALUE;
    	// 	}
    	// 	if (directionVertical === 0) {
    	// 		if (list[i] === global.KEY_UP) directionVertical -= Number.MAX_VALUE;
    	// 		else if (list[i] === global.KEY_DOWN) directionVertical += Number.MAX_VALUE;
    	// 	}
    	// }
    	this.target.x += directionHorizontal;
    	this.target.y += directionVertical;
        global.target = this.target;
    }

    directional(key) {
    	return this.horizontal(key) || this.vertical(key);
    }

    horizontal(key) {
    	return key === global.KEY_LEFT || key === global.KEY_RIGHT || key === global.KEY_A || key===global.KEY_D;
    }

    vertical(key) {
    	return key === global.KEY_DOWN || key === global.KEY_UP;
    }

    // Register when the mouse goes off the canvas.
    outOfBounds() {
        if (!global.continuity) {
            this.parent.target = { x : 0, y: 0 };
            global.target = this.parent.target;
        }
    }

    gameInput(mouse) {
    	if (!this.directionLock) {
            if (findPlayer(currentPlayer) && findPlayer(currentPlayer).longitude){
                const mx = mouse.offsetX-this.width/2;
                const my = mouse.offsetY-this.height/2;
                let render_angle = Math.PI/2 + findPlayer(currentPlayer).longitude * Math.PI/180; // So that the current player is always upright
                const cos = Math.cos(render_angle);
                const sin = Math.sin(render_angle);

                const X = cos * mx - sin *my;
                const Y = sin * mx + cos * my;

                //console.log(mouse.offsetX, mouse.offsetY,mx,my,X,Y)
                // this.parent.target.x = mouse.clientX - this.width / 2;
                // this.parent.target.y = mouse.clientY - this.height / 2;
                this.parent.target.x = X;
                this.parent.target.y = Y;
                global.target = this.parent.target;
            }

    	}
    }

    touchInput(touch) {
        touch.preventDefault();
        touch.stopPropagation();
    	if (!this.directionLock) {
    		this.parent.target.x = touch.touches[0].clientX - this.width / 2;
    		this.parent.target.y = touch.touches[0].clientY - this.height / 2;
            global.target = this.parent.target;
    	}
    }

    // Chat command callback functions.
    keyInput(event) {
    	var key = event.which || event.keyCode;
    	if (key === global.KEY_FIREFOOD && this.parent.reenviar) {
            this.parent.socket.emit('fire_gun');
            this.parent.reenviar = false;
        }
        else if (key === global.KEY_SPLIT && this.parent.reenviar) {
            document.getElementById('split_cell').play();
            this.parent.socket.emit('2');
            this.parent.reenviar = false;
        }
        else if (key === global.KEY_CHAT) {
            document.getElementById('chatInput').focus();
        }
        if (event.key === global.KEY_NEXT_BULLET){
            this.parent.socket.emit('next_bullet');
        }
    }
}

//module.exports = Canvas;
