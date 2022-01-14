//var io = require('socket.io-client');
//var ChatClient = require('./chat-client');
//var Canvas = require('./canvas');
//var global = require('./global');

const playerNameInput = document.getElementById('playerNameInput');
let socket;
let reason;

const debug = function (args) {
    if (console && console.log) {
        console.log(args);
    }
};

if ( /Android|webOS|iPhone|iPad|iPod|BlackBerry/i.test(navigator.userAgent) ) {
    global.mobile = true;
}

function startGame(type) {
    global.playerName = playerNameInput.value.replace(/(<([^>]+)>)/ig, '').substring(0,25);
    global.playerType = type;

    global.screenWidth = window.innerWidth;
    global.screenHeight = window.innerHeight;

    document.getElementById('startMenuWrapper').style.maxHeight = '0px';
    document.getElementById('gameAreaWrapper').style.opacity = 1;
    if (!socket) {
        socket = io({query:"type=" + type});
        setupSocket(socket);
    }
    if (!global.animLoopHandle)
        animloop();
    socket.emit('respawn');
    window.chat.socket = socket;
    window.chat.registerFunctions();
    window.canvas.socket = socket;
    global.socket = socket;
}

// Checks if the nick chosen contains valid alphanumeric characters (and underscores).
function validNick() {
    const regex = /^\w*$/;
    debug('Regex Test', regex.exec(playerNameInput.value));
    return regex.exec(playerNameInput.value) !== null;
}

function findPlayer(playerSid){
    for (let user of users){
        if (user.id === playerSid){
            return user;
        }
    }
    return undefined;
}

window.onload = function() {

    if (!socket) {
        socket = io({query:"type=player"});
        setupSocket(socket);
    }

    const btn = document.getElementById('startButton');
    const nickErrorText = document.querySelector('#startMenu .input-error');
    const createRoomButton = document.getElementById('createRoomButton');

    btn.onclick = function () {

        // Checks if the nick is valid.
        if (validNick()) {
            nickErrorText.style.opacity = 0;
            startGame('player');
        } else {
            nickErrorText.style.opacity = 1;
        }
    };

    // TODO: when the client receives a 'room_already_exists_error' event from socket-io, inform the user somehow.
    createRoomButton.addEventListener('click', function (){
        socket.emit('create_room', {name:document.getElementById('roomNameInput').value});
    });

    const settingsMenu = document.getElementById('settingsButton');
    const settings = document.getElementById('settings');
    const instructions = document.getElementById('instructions');

    settingsMenu.onclick = function () {
        if (settings.style.maxHeight === '300px') {
            settings.style.maxHeight = '0px';
        } else {
            settings.style.maxHeight = '300px';
        }
    };

    playerNameInput.addEventListener('keypress', function (e) {
        const key = e.which || e.keyCode;

        if (key === global.KEY_ENTER) {
            if (validNick()) {
                nickErrorText.style.opacity = 0;
                startGame('player');
            } else {
                nickErrorText.style.opacity = 1;
            }
        }
    });
};

// TODO: Break out into GameControls.

const foodConfig = {
    border: 10,
};

let playerConfig = {
    border: 6,
    textColor: '#FFFFFF',
    textBorder: '#000000',
    textBorderSize: 3,
    defaultSize: 30
};

let player = {
    id: -1,
    x: global.screenWidth / 2,
    y: global.screenHeight / 2,
    screenWidth: global.screenWidth,
    screenHeight: global.screenHeight,
    target: {x: global.screenWidth / 2, y: global.screenHeight / 2}
};
global.player = player;

let foods = [];
let viruses = [];
let fireFood = [];
let users = [];
let explosions = [];
let planets = []
let bullets = [];
let trajectory = [];
let target = {x: player.x, y: player.y};
let room_names=[];
global.target = target;
let turns_enabled = false;  // Is the game-mode turns-enabled or live?
let particles = []; //List of particles to render
let currentPlayer = '';

window.canvas = new Canvas();
window.chat = new ChatClient();

const visibleBorderSetting = document.getElementById('visBord');
visibleBorderSetting.onchange = settings.toggleBorder;

// var showMassSetting = document.getElementById('showMass');
// showMassSetting.onchange = settings.toggleMass;

const continuitySetting = document.getElementById('continuity');
continuitySetting.onchange = settings.toggleContinuity;

// var roundFoodSetting = document.getElementById('roundFood');
// roundFoodSetting.onchange = settings.toggleRoundFood;

const c = window.canvas.cv;
const graph = c.getContext('2d');
const health_ctx = document.getElementById('cvs-healthbar').getContext('2d');
const inventory_cv = document.getElementById('cvs-inventory');
const inventory_ctx = inventory_cv.getContext('2d');

$( "#feed" ).click(function() {
    socket.emit('1');
    window.canvas.reenviar = false;
});

$( "#split" ).click(function() {
    socket.emit('2');
    window.canvas.reenviar = false;
});

//load images
function load_image(url){
    let img = new Image();
    img.src = url
    return img
}

sprites = {
    GREYBODY1_SPRITE: load_image('/img/tanks_tankGrey_body1.png'),
    TURRET1_SPRITE: load_image('/img/tanks_turret1.png'),
    TREADS1_SPRITE: load_image('/img/tanks_tankTracks1.png'),
    EXPLOSION1_SPRITE: load_image('/img/tank_explosion1.png'),
    HPBAR_SPRITE: load_image('/img/hp_bar.png'),
    HPSEGMENT_SPRITE: load_image('/img/hp_segment.png'),
    BULLET_SPRITE: load_image('/img/BulletSprites/bullet.png'),
    BULLET2_SPRITE: load_image('/img/BulletSprites/bullet2.png'),
    BULLET3_SPRITE: load_image('/img/BulletSprites/tank_bullet1.png'),
    BULLET4_SPRITE: load_image('/img/BulletSprites/tank_bullet2.png'),
    BULLET5_SPRITE: load_image('/img/BulletSprites/tank_bullet3.png'),
    BULLET6_SPRITE: load_image('/img/BulletSprites/tank_bullet4.png'),
    BULLET7_SPRITE: load_image('/img/BulletSprites/tank_bullet5.png'),
    BULLET8_SPRITE: load_image('/img/BulletSprites/tank_bullet6.png'),
    BULLET9_SPRITE: load_image('/img/BulletSprites/bullet7.png'),
    BULLET10_SPRITE: load_image('/img/BulletSprites/bullet8.png'),
    BULLET11_SPRITE: load_image('/img/BulletSprites/bullet9.png'),
    BULLET12_SPRITE: load_image('/img/BulletSprites/bullet10.png'),
    MINE_SPRITE : load_image('/img/BulletSprites/tanks_mineOn.png'),
    SPARK_SPRITE: load_image('/img/spark.png')
}

class Particle{
    constructor(sprite, position, life_span, tint,
                max_scale=1, scale_in_frac=0,
                fade_in_frac=0, fad_out_frac=0){
        this.sprite = sprite;
        this.position = position;
        this.life_span = life_span;
        this.max_scale = max_scale;
        this.scale_in_frac = scale_in_frac;
        this.fade_in_frac = fade_in_frac;
        this.fad_out_frac = fad_out_frac;
        this.tint = tint;
        this.time_created = Date.now();


        this.dead = false;
        this.image = sprites[sprite];
    }

    time_check(){
        if (this.life_span < Date.now() - this.time_created){
            this.dead = true;
        }
        return this.dead;
    }

    draw(context){
        const center = getCenterXAndY(this.position);
        rotateAndDrawImage(context, this.image, 0, center.x, center.y);
    }
}

//grab sounds from the html
function load_sound(id){
    return document.getElementById(id);
}

sounds = {
    GUN_SOUND: load_sound('SoundType.GUN_SOUND'),
    RICOCHET_SOUND: load_sound('SoundType.RICOCHET_SOUND'),
    OW_SOUND: load_sound('SoundType.OW_SOUND'),
    CLANG_SOUND: load_sound('SoundType.CLANG_SOUND'),
    EXPLOSION1_SOUND: load_sound('SoundType.EXPLOSION1_SOUND'),
    EXPLOSION3_SOUND: load_sound('SoundType.EXPLOSION3_SOUND'),
    EXPLOSION7_SOUND: load_sound('SoundType.EXPLOSION7_SOUND'),
    SHOOT_SOUND: load_sound('SoundType.SHOOT_SOUND'),
    SHOOT2_SOUND: load_sound('SoundType.SHOOT2_SOUND'),
    SCIFI_MUSIC: load_sound('SoundType.SCIFI_MUSIC'),
    NEWDAWN_MUSIC: load_sound('SoundType.NEWDAWN_MUSIC')
}

function playSound(soundtype){
    //If soundtype is empty, we shouldn't play a sound.
    if (soundtype) {
        //Ignore 'SoundType.' in the front of the name.
        sounds[soundtype.substring(10)].play();
    }
}

function loopSound(soundtype){
    //If soundtype is empty, we shouldn't play a sound.
    if (soundtype) {
        //Ignore 'SoundType.' in the front of the name.
        const sound = sounds[soundtype.substring(10)];
        sound.loop = true;
        sound.play();
    }
}


function stopAllSounds(){
    for (const [name, sound] of Object.entries(sounds)){
        sound.loop = false;
        sound.pause();
        sound.currentTime = 0;
    }
}

//Start menu music immediately after click (Chrome won't play audio until the user has interacted with the domain.)
document.body.addEventListener('click', ()=>{loopSound('Soundtype.NEWDAWN_MUSIC')}, {once: true})


//Add html elements to the given element that
function add_rooms_to_list(room_name, element){
    const room_input = document.createElement('input');
    const label = document.createElement('label');
    label.htmlFor=room_name;
    label.innerHTML=room_name;
    room_input.type = 'radio';
    room_input.id=room_input.value=room_name;
    room_input.name='room_list_input';
    room_input.addEventListener('change', update_play_button);
    element.appendChild(room_input);
    element.appendChild(label);
    element.appendChild(document.createElement('br'));
}


//Check if any room is selected
function check_if_room_selected(){
    return ($('input[name=room_list_input]:checked').length > 0)
}

function update_play_button(){
    if (check_if_room_selected()){
        document.getElementById('startButton').disabled = false;
    }
}

function returnToMenu(){
    document.getElementById('gameAreaWrapper').style.opacity = 0;
    document.getElementById('startMenuWrapper').style.maxHeight = '1000px';
    global.died = false;
    if (global.animLoopHandle) {
        window.cancelAnimationFrame(global.animLoopHandle);
        global.animLoopHandle = undefined;
    }
}


// socket stuff.
function setupSocket(socket) {
    socket.emit('request_rooms');

    // Handle ping.
    socket.on('pongcheck', function () {
        let latency = Date.now() - global.startPingTime;
        debug('Latency: ' + latency + 'ms');
        window.chat.addSystemLine('Ping: ' + latency + 'ms');
    });

    // Handle error.
    socket.on('connect_failed', function () {
        socket.close();
        global.disconnected = true;
    });

    socket.on('disconnect', function () {
        socket.close();
        global.disconnected = true;
    });

    socket.on('room_close', function(){
        global.gameStart = false;
        global.roomClosing = true;
        planets = []
        window.setTimeout(returnToMenu, 7500);
    });

    socket.on('room_list', (list)=>{
        console.log(list);
        room_names = list;
        const room_list_ul = document.getElementById('room-list')
        const checked_value_element = $('input[name=room_list_input]:checked')[0]
        room_list_ul.innerHTML = '';
        room_names.forEach((element) => add_rooms_to_list(element, room_list_ul))
        if (checked_value_element){
            const previously_selected = $(`input[name=room_list_input][value=${checked_value_element.value}]`)[0]
            if (previously_selected){
                previously_selected.checked = true;
            }
        }
    });

    // Handle connection.
    socket.on('welcome', function (playerSettings) {
        player = playerSettings;
        player.name = global.playerName;
        player.screenWidth = global.screenWidth;
        player.screenHeight = global.screenHeight;
        player.target = window.canvas.target;
        player.new_room = $('input[name=room_list_input]:checked')[0].value; //Connect to the room with the correct name
        global.player = player;
        window.chat.player = player;
        socket.emit('gotit', player);
        global.gameStart = true;
        debug('Game started at: ' + global.gameStart);
        window.chat.addSystemLine('Connected to the game!');
        window.chat.addSystemLine('Type <b>-help</b> for a list of commands.');
        if (global.mobile) {
            document.getElementById('gameAreaWrapper').removeChild(document.getElementById('chatbox'));
        }
		c.focus();
        //Play game music
        stopAllSounds();
        loopSound('SoundType.SCIFI_MUSIC');
    });

    socket.on('gameSetup', function(data) {
        global.gameWidth = data.gameWidth;
        global.gameHeight = data.gameHeight;
        resize();
    });

    socket.on('playerDied', function (data) {
        window.chat.addSystemLine('{GAME} - <b>' + (data.name.length < 1 ? 'An unnamed tank' : data.name) + '</b> has died.');
    });

    socket.on('playerDisconnect', function (data) {
        window.chat.addSystemLine('{GAME} - <b>' + (data.name.length < 1 ? 'An unnamed tank' : data.name) + '</b> disconnected.');
    });

    socket.on('playerJoin', function (data) {
        window.chat.addSystemLine('{GAME} - <b>' + (data.name.length < 1 ? 'An unnamed tank' : data.name) + '</b> joined.');
    });

    socket.on('serverMSG', function (data) {
        window.chat.addSystemLine(data);
    });

    // Chat.
    socket.on('serverSendPlayerChat', function (data) {
        window.chat.addChatLine(data.sender, data.message, false);
    });

    socket.on('initial', function(data){
        console.log('initial', data)
        planets = [];
        users=[];
        if (data.sprite === 'SpriteType.PLANET_SPRITE'){
            planets.push(data)
        } else if (data.sprite === 'SpriteType.GREY1_SPRITE'){
            console.log('pushing user', data.id)
            users.push(data)
        }
    });

    socket.on('turns_enabled', function(data){
        turns_enabled = data.turns_enabled;
    });

    socket.on('update', function(data){
        //console.log('updating', data)
        if (data.sprite === 'SpriteType.PLANET_SPRITE'){
            //console.log(data)
            let planet;
            for (let j = 0; j < planets.length; j++){
                if (planets[j].id === data.id){
                    planet = planets[j];
                }
            }
            if (planet) {
                for (let i = 0; i < data.update.length; i++) {
                    let index = data.update[i][0];
                    planet.altitudes[index] = data.update[i][1];
                }
            }
        }

        else if (data.sprite === 'SpriteType.BULLET_SPRITE') {
            //console.log('got bullet')
            bullets.push(data)
        } else {
            console.log('weird update:', data)
        }
    })

    socket.on('update-bullets', function(bulletList){
        bullets = bulletList
    });
    socket.on('update-tanks', function(tankList){
        //console.log('Receiving tank updates', Date.now())
        users = tankList.filter((t)=>{return typeof(t.sprite) != 'undefined'});
        for (let i = 0; i < users.length; i++) {
            if (users[i].id === socket.id) {
                //console.log('found player')
                let health_inventory_changes = false;
                const xoffset = player.x - users[i].x;
                const yoffset = player.y - users[i].y;

                player.x = users[i].x;
                player.y = users[i].y;
                player.hue = users[i].hue;
                player.xoffset = isNaN(xoffset) ? 0 : xoffset;
                player.yoffset = isNaN(yoffset) ? 0 : yoffset;
                if (player.health !== users[i].health){
                    player.health = users[i].health;
                    health_inventory_changes = true;
                }
                if (player.selected_bullet !== users[i].selected_bullet){
                    player.selected_bullet = users[i].selected_bullet;
                    health_inventory_changes = true;
                }
                if (player.bullet_counts !== users[i].bullet_counts){
                    player.bullet_counts = users[i].bullet_counts;
                    health_inventory_changes = true;
                }
                player.bullet_sprites = users[i].bullet_sprites;
                if( health_inventory_changes){
                    drawHPBar(player.health);
                    drawInventory();
                }
            }

        }
    });

    socket.on('update-explosions', function(explosionsList){
        explosions = explosionsList
    })
    // Handle movement.
    socket.on('-serverTellPlayerMove', function (data) {
        let userData = data[0];
        let foodsList = data[1];
        let massList = data[2];
        let virusList = data[3];
        let playerData;
        for(let i =0; i< userData.length; i++) {
            if(typeof(userData[i].id) == "undefined") {
                playerData = userData[i];
                i = userData.length;
            }
        }
        if(global.playerType === 'player') {
            const xoffset = player.x - playerData.x;
            const yoffset = player.y - playerData.y;

            player.x = playerData.x;
            player.y = playerData.y;
            player.hue = playerData.hue;
            player.xoffset = isNaN(xoffset) ? 0 : xoffset;
            player.yoffset = isNaN(yoffset) ? 0 : yoffset;
        }
        foods = foodsList;
        viruses = virusList;
        fireFood = massList;
    });

    // Death.
    socket.on('RIP', function () {
        global.gameStart = false;
        global.died = true;
        planets = []
        window.setTimeout(returnToMenu, 2500);
    });

    socket.on('kick', function (data) {
        global.gameStart = false;
        reason = data;
        global.kicked = true;
        socket.close();
    });

    socket.on('virusSplit', function (virusCell) {
        socket.emit('2', virusCell);
        reenviar = false;
    });

    socket.on('trajectory', function(data){
        trajectory = data.positions;
    });

    socket.on('next-turn', function(data){
       currentPlayer = data.current_player;
    });
}

function drawCircle(centerX, centerY, radius, sides) {
    let theta = 0;
    let x = 0;
    let y = 0;

    graph.beginPath();

    for (var i = 0; i < sides; i++) {
        theta = (i / sides) * 2 * Math.PI;
        x = centerX + radius * Math.sin(theta);
        y = centerY + radius * Math.cos(theta);
        graph.lineTo(x, y);
    }

    graph.closePath();
    graph.stroke();
    graph.fill();
}

function rotateAndDrawImage(context, image, angleInRadians, positionX, positionY, axisX=0, axisY=0, imageWidth=1, imageHeight=1){
    context.save()
    context.translate( positionX , positionY);
    context.rotate(angleInRadians);
    context.translate(- image.width/2, - image.height/2)
    context.drawImage( image, -axisX, -axisY , imageWidth * image.width, imageHeight*image.height);
    context.restore()
}

function getCenterXAndY(object){
    let center_object;
    if (turns_enabled && bullets.length){
        center_object = bullets[0];
    } else {
        const currentPlayerInfo = findPlayer(currentPlayer);
        if (currentPlayerInfo) {
            center_object = currentPlayerInfo;
        } else {
            center_object = player;
        }
    }
    return {x:object.x - center_object.x + global.screenWidth/2,
            y:object.y - center_object.y + global.screenHeight/2}
}

function drawExplosion(explosion){
    const center = getCenterXAndY(explosion)

    let spriteName = explosion.sprite.substring(11);

    drawCircle(center.x, center.y, explosion.radius, 16);

    rotateAndDrawImage(graph, sprites[spriteName], 0, center.x, center.y, 0, 0);

    // Play the sound
    playSound(explosion.sound)

}





function drawHPBar(health){
    //Clear
    health_ctx.clearRect(0, 0, global.screenWidth, global.screenHeight);
    // Draw bar
    health_ctx.drawImage(sprites.HPBAR_SPRITE, 0, 0);

    //Draw segments
    let current_x = 8
    for (let i=0; i < health/4; i++){
        health_ctx.drawImage(sprites.HPSEGMENT_SPRITE,current_x, 40);
        current_x += sprites.HPSEGMENT_SPRITE.width;
    }

    // Text
    health_ctx.fillStyle = "#ff8c00";
    health_ctx.textAlign = "center";
    health_ctx.font = "24px Arial";
    health_ctx.fillText(health + "%", 250,90);

    //TODO: Fuel bar
}

function drawInventory(){
    //Clear
    inventory_ctx.clearRect(0, 0, global.screenWidth, global.screenHeight);

    let selectedIndex = player.selected_bullet;
    inventory_ctx.fillStyle = "#ffffffff";
    inventory_ctx.textAlign = "left";
    inventory_ctx.font = "24px Arial";
    //go through each available bullet for player
    for (let i=0; i < 5; i++){//only display 5 bullets at a time
        let bulletIndex = i + selectedIndex;

        console.log('i=',i, bulletIndex)
        if (player.bullet_counts && !isNaN(bulletIndex)){
            console.log(player.bullet_counts)
            // Make sure our index is within the range of available bullets
            if (bulletIndex >= player.bullet_counts.length)
                bulletIndex -= player.bullet_counts.length;

            //set sprite and draw on side of screen
            let sprite_name = player.bullet_sprites[bulletIndex].substring(11);
            let sprite = sprites[sprite_name];



            let angle = i===0 ? Math.PI/4 : 0
            console.log(sprite, angle);
            rotateAndDrawImage(inventory_ctx, sprite, angle, 50, global.screenHeight/3 - 30 + (i*50));

            //Draw Bullet counts
            if (bulletIndex === 0 || bulletIndex === 1)
                inventory_ctx.fillText("Infinite", 100, global.screenHeight/3 - 30 + (i * 50));
            else
                inventory_ctx.fillText(player.bullet_counts[bulletIndex], 100, global.screenHeight/3- 30 + (i * 50));

            if (i===0)
                inventory_ctx.fillText("<-", 175, global.screenHeight/3 - 30 + (i * 50));
        }

    }
}

function drawTank(tank){
    /*let centerX = tank.x - player.x + global.screenWidth / 2 ;
    let centerY = tank.y - player.y + global.screenHeight / 2 ;*/
    const center = getCenterXAndY(tank)
    const [centerX, centerY] = [center.x, center.y]

    let difference_x = tank.x - tank.planet_x;
    let difference_y = tank.y - tank.planet_y;
    let norm_diff = Math.sqrt(Math.pow(difference_x,2) + Math.pow(difference_y,2));
    difference_x /= norm_diff;
    difference_y /= norm_diff;

    //Adjust for the fact that centerX and centerY is currently actually the /bottom/ of the tank, but we need them to represent the center
    //centerX += difference_x * (sprites.GREYBODY1_SPRITE.height/2 - 1);
    //centerY += difference_y * (sprites.GREYBODY1_SPRITE.height/2 - 1);

    // Turret
    let turret_angle = Math.PI + (tank.angle + tank.longitude) * Math.PI/180;
    rotateAndDrawImage(graph, sprites.TURRET1_SPRITE, turret_angle, centerX, centerY, 0, 0);

    // Treads
    let render_angle = Math.PI + tank.longitude * Math.PI/180;
    let height = sprites.TREADS1_SPRITE.height
    let tread_x =  .3 * height * difference_x;
    let tread_y =  .3 * height * difference_y;
    rotateAndDrawImage(graph, sprites.TREADS1_SPRITE, render_angle, centerX -tread_x, centerY-tread_y, 0, 0);

    // Tank Body
    rotateAndDrawImage(graph, sprites.GREYBODY1_SPRITE, render_angle, centerX, centerY, 0, 0);

    //Draw line from planet core to center of tank, for debugging
    // graph.beginPath();
    // graph.moveTo(centerX,centerY);
    // graph.lineTo(centerX - norm_diff * difference_x, centerY - norm_diff * difference_y)
    // graph.stroke();

    //Play Sound
    playSound(tank.sound);


}

function drawPlanet(planet){
    /*let centerX = planet.x - player.x + global.screenWidth / 2
    let centerY = planet.y - player.y + global.screenHeight / 2*/
    const center = getCenterXAndY(planet)
    const [centerX, centerY] = [center.x, center.y]

    //graph.strokeStyle = 'hsl(' + planet.hue + ', 100%, 45%)';
    graph.strokeStyle= 'grey';
    let gradient = graph.createRadialGradient(centerX, centerY, planet.core_radius, centerX, centerY, planet.sealevel_radius);
    gradient.addColorStop(0, "yellow");
    gradient.addColorStop(1 - 5000/6370, '#E2D61D') //inner core
    gradient.addColorStop(1 - 4000/6370, '#E2A91D') //upper core
    gradient.addColorStop(1 - 2500/6370, '#F59623') // lower mantle
    gradient.addColorStop(1 - 1000/6370, '#C23A0A') // upper mantle
    gradient.addColorStop(1 - 35/6370, 'grey');  // crust
    gradient.addColorStop(1 - 0/6370, 'grey');  // crust
    //gradient.addColorStop(1, 'hsl(' + planet.hue + ', 100%, 50%)');
    //graph.fillStyle = 'hsl(' + planet.hue + ', 100%, 50%)';
    graph.fillStyle = gradient
    graph.lineWidth = foodConfig.border;

    let theta = 0;
    let x = 0;
    let y = 0;

    graph.beginPath();



    for (let i = 0; i < planet.number_of_altitudes; i++) {
        theta = (i / planet.number_of_altitudes) * 2 * Math.PI;
        x = centerX + planet.altitudes[i] * Math.cos(theta);
        y = centerY + planet.altitudes[i] * Math.sin(theta);
        graph.lineTo(x, y);
    }

    graph.closePath();
    graph.stroke();
    graph.fill();


    //Planet center for debugging
    // graph.fillStyle = 'hsl(' + planet.hue + ', 100%, 50%)';
    // graph.fillRect(centerX- 5/2, centerY-5/2,5,5);
}

function drawBullet(bullet){
    const center = getCenterXAndY(bullet)
    let sprite_name = bullet.sprite.substring(11); //The string passed includes 'SpriteType.' before the name
    rotateAndDrawImage(graph, sprites[sprite_name], bullet.roll, center.x, center.y,0,0);
    playSound(bullet.sound);
    // Every so often, add a particle to show the trajectory
    // 10 times a second add a particle
    if (( Date.now() % 100)<50){
        particles.push(new Particle('BULLET2_SPRITE', {x:bullet.x, y:bullet.y}, 10000, bullet.hue, .1));
    }
}


function drawgrid() {
     graph.lineWidth = 1;
     graph.strokeStyle = global.lineColor;
     graph.globalAlpha = 0.15;
     graph.beginPath();

    for (let x = global.xoffset - player.x; x < global.screenWidth; x += global.screenHeight / 18) {
        graph.moveTo(x, 0);
        graph.lineTo(x, global.screenHeight);
    }

    for (let y = global.yoffset - player.y ; y < global.screenHeight; y += global.screenHeight / 18) {
        graph.moveTo(0, y);
        graph.lineTo(global.screenWidth, y);
    }

    graph.stroke();
    graph.globalAlpha = 1;
}

function drawborder() {
    graph.lineWidth = 1;
    graph.strokeStyle = playerConfig.borderColor;

    // Left-vertical.
    if (player.x <= global.screenWidth/2) {
        graph.beginPath();
        graph.moveTo(global.screenWidth/2 - player.x, 0 ? player.y > global.screenHeight/2 : global.screenHeight/2 - player.y);
        graph.lineTo(global.screenWidth/2 - player.x, global.gameHeight + global.screenHeight/2 - player.y);
        graph.strokeStyle = global.lineColor;
        graph.stroke();
    }

    // Top-horizontal.
    if (player.y <= global.screenHeight/2) {
        graph.beginPath();
        graph.moveTo(0 ? player.x > global.screenWidth/2 : global.screenWidth/2 - player.x, global.screenHeight/2 - player.y);
        graph.lineTo(global.gameWidth + global.screenWidth/2 - player.x, global.screenHeight/2 - player.y);
        graph.strokeStyle = global.lineColor;
        graph.stroke();
    }

    // Right-vertical.
    if (global.gameWidth - player.x <= global.screenWidth/2) {
        graph.beginPath();
        graph.moveTo(global.gameWidth + global.screenWidth/2 - player.x,
                     global.screenHeight/2 - player.y);
        graph.lineTo(global.gameWidth + global.screenWidth/2 - player.x,
                     global.gameHeight + global.screenHeight/2 - player.y);
        graph.strokeStyle = global.lineColor;
        graph.stroke();
    }

    // Bottom-horizontal.
    if (global.gameHeight - player.y <= global.screenHeight/2) {
        graph.beginPath();
        graph.moveTo(global.gameWidth + global.screenWidth/2 - player.x,
                     global.gameHeight + global.screenHeight/2 - player.y);
        graph.lineTo(global.screenWidth/2 - player.x,
                     global.gameHeight + global.screenHeight/2 - player.y);
        graph.strokeStyle = global.lineColor;
        graph.stroke();
    }
}

function drawParticles(){
    particles = particles.filter(particle => !particle.time_check()); // Delete all of the dead particles
    // for (let particle of particles){
    //     particle.draw(graph);
    // }
    // graph.lineWidth = "5";
    // graph.setLineDash([5,15]);
    // graph.beginPath();
    // graph.strokeStyle = '';
    // let current_color = '';
    for (let i in particles){
        const point = {x:particles[i].position.x, y:particles[i].position.y}
        const center = getCenterXAndY(point);
        // console.log(center, graph.strokeStyle);
        // if (current_color !== particles[i].tint) {
        //     graph.strokeStyle = particles[i].tint || 'red';
        //     current_color = particles[i].tint || 'red';
        //     graph.moveTo(center.x, center.y);
        // } else {
        //     graph.lineTo(center.x, center.y);
        // }
        graph.fillStyle = particles[i].tint || 'red';
        graph.fillRect(center.x, center.y, 5,5);
    }
    // graph.stroke();
    // graph.setLineDash([]); //Reset the dashed lines
}

function drawTrajectory(trajectory){
    const current_tank = findPlayer(currentPlayer);
    graph.strokeStyle = current_tank ? (current_tank.hue || 'red') : 'red';
    graph.lineWidth="5";
    graph.setLineDash([5,15]);
    graph.beginPath();
    for (let i = 0; i < trajectory.length; i++){
        const point = {x:trajectory[i][0], y:trajectory[i][1]}
        const center = getCenterXAndY(point);
        if (i === 0) {
            graph.moveTo(center.x, center.y);
        } else {
            graph.lineTo(center.x, center.y);
        }

    }
    graph.stroke();
    graph.setLineDash([]); //Reset the dashed lines

}

window.requestAnimFrame = (function() {
    return  window.requestAnimationFrame       ||
            window.webkitRequestAnimationFrame ||
            window.mozRequestAnimationFrame    ||
            window.msRequestAnimationFrame     ||
            function( callback ) {
                window.setTimeout(callback, 1000 / 60);
            };
})();

window.cancelAnimFrame = (function(handle) {
    return  window.cancelAnimationFrame     ||
            window.mozCancelAnimationFrame;
})();

function animloop() {
    global.animLoopHandle = window.requestAnimFrame(animloop);
    gameLoop();
}

function gameLoop() {
    if (global.died) {
        graph.resetTransform();
        graph.fillStyle = '#333333';
        graph.fillRect(0, 0, global.screenWidth, global.screenHeight);

        graph.textAlign = 'center';
        graph.fillStyle = '#FFFFFF';
        graph.font = 'bold 30px sans-serif';
        graph.fillText('You died!', global.screenWidth / 2, global.screenHeight / 2);
    }
    else if (global.roomClosing) {
        graph.resetTransform();
        graph.fillStyle = '#333333';
        graph.fillRect(0, 0, global.screenWidth, global.screenHeight);

        graph.textAlign = 'center';
        graph.fillStyle = '#FFFFFF';
        graph.font = 'bold 30px sans-serif';
        graph.fillText('Room is closing!', global.screenWidth / 2, global.screenHeight / 2);
    }
    else if (!global.disconnected) {
        if (global.gameStart) {
            //Reset all transformations
            graph.resetTransform();
            graph.clearRect(0, 0, global.screenWidth, global.screenHeight);

            //Rotate the entire screen so that the current player is upright.
            if (findPlayer(currentPlayer) && findPlayer(currentPlayer).longitude){
                let render_angle = Math.PI/2 + findPlayer(currentPlayer).longitude * Math.PI/180; // So that the current player is always upright
                graph.translate(global.screenWidth/2, global.screenHeight/2);
                graph.rotate(-render_angle);
                graph.translate(-global.screenWidth/2, -global.screenHeight/2);
            }

            planets.forEach(drawPlanet);
            drawTrajectory(trajectory); //Trajectory before users, so that it's not renders atop tanks
            users.forEach(drawTank);
            bullets.forEach(drawBullet);
            drawParticles();
            explosions.forEach(drawExplosion);
            //drawHPBar(player.health)
            //drawInventory();

            if (global.borderDraw) {
                drawborder();
            }
            socket.emit('0', window.canvas.target); // playerSendTarget "Heartbeat".
        } else {
            graph.fillStyle = '#333333';
            graph.fillRect(0, 0, global.screenWidth, global.screenHeight);

            graph.textAlign = 'center';
            graph.fillStyle = '#FFFFFF';
            graph.font = 'bold 30px sans-serif';
            graph.fillText('Game Over!', global.screenWidth / 2, global.screenHeight / 2);
        }
    } else {
        graph.fillStyle = '#333333';
        graph.fillRect(0, 0, global.screenWidth, global.screenHeight);

        graph.textAlign = 'center';
        graph.fillStyle = '#FFFFFF';
        graph.font = 'bold 30px sans-serif';
        if (global.kicked) {
            if (reason !== '') {
                graph.fillText('You were kicked for:', global.screenWidth / 2, global.screenHeight / 2 - 20);
                graph.fillText(reason, global.screenWidth / 2, global.screenHeight / 2 + 20);
            }
            else {
                graph.fillText('You were kicked!', global.screenWidth / 2, global.screenHeight / 2);
            }
        }
        else {
              graph.fillText('Disconnected!', global.screenWidth / 2, global.screenHeight / 2);
        }
    }
}

window.addEventListener('resize', resize);

function resize() {
    if (!socket) return;

    player.screenWidth = c.width = inventory_cv.width = global.screenWidth = global.playerType === 'player' ? window.innerWidth : global.gameWidth;
    player.screenHeight = c.height = inventory_cv.height = global.screenHeight = global.playerType === 'player' ? window.innerHeight : global.gameHeight;

    if (global.playerType === 'spectate') {
        player.x = global.gameWidth / 2;
        player.y = global.gameHeight / 2;
    }

    socket.emit('windowResized', { screenWidth: global.screenWidth, screenHeight: global.screenHeight });
}
