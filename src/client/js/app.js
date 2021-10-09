//var io = require('socket.io-client');
//var ChatClient = require('./chat-client');
//var Canvas = require('./canvas');
//var global = require('./global');

var playerNameInput = document.getElementById('playerNameInput');
var socket;
var reason;

var debug = function(args) {
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
    var regex = /^\w*$/;
    debug('Regex Test', regex.exec(playerNameInput.value));
    return regex.exec(playerNameInput.value) !== null;
}

window.onload = function() {

    var btn = document.getElementById('startButton'),
        btnS = document.getElementById('spectateButton'),
        nickErrorText = document.querySelector('#startMenu .input-error');

    btnS.onclick = function () {
        startGame('spectate');
    };

    btn.onclick = function () {

        // Checks if the nick is valid.
        if (validNick()) {
            nickErrorText.style.opacity = 0;
            startGame('player');
        } else {
            nickErrorText.style.opacity = 1;
        }
    };

    var settingsMenu = document.getElementById('settingsButton');
    var settings = document.getElementById('settings');
    var instructions = document.getElementById('instructions');

    settingsMenu.onclick = function () {
        if (settings.style.maxHeight == '300px') {
            settings.style.maxHeight = '0px';
        } else {
            settings.style.maxHeight = '300px';
        }
    };

    playerNameInput.addEventListener('keypress', function (e) {
        var key = e.which || e.keyCode;

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

var foodConfig = {
    border: 10,
};

var playerConfig = {
    border: 6,
    textColor: '#FFFFFF',
    textBorder: '#000000',
    textBorderSize: 3,
    defaultSize: 30
};

var player = {
    id: -1,
    x: global.screenWidth / 2,
    y: global.screenHeight / 2,
    screenWidth: global.screenWidth,
    screenHeight: global.screenHeight,
    target: {x: global.screenWidth / 2, y: global.screenHeight / 2}
};
global.player = player;

var foods = [];
var viruses = [];
var fireFood = [];
var users = [];
let explosions = [];
let planets = []
let bullets = [];
let trajectory = [];
var leaderboard = [];
var target = {x: player.x, y: player.y};
global.target = target;

window.canvas = new Canvas();
window.chat = new ChatClient();

var visibleBorderSetting = document.getElementById('visBord');
visibleBorderSetting.onchange = settings.toggleBorder;

// var showMassSetting = document.getElementById('showMass');
// showMassSetting.onchange = settings.toggleMass;

var continuitySetting = document.getElementById('continuity');
continuitySetting.onchange = settings.toggleContinuity;

// var roundFoodSetting = document.getElementById('roundFood');
// roundFoodSetting.onchange = settings.toggleRoundFood;

var c = window.canvas.cv;
var graph = c.getContext('2d');
var health_ctx = document.getElementById('cvs-healthbar').getContext('2d');

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
    MINE_SPRITE : load_image('/img/BulletSprites/tanks_mineOn.png')
}





// socket stuff.
function setupSocket(socket) {
    // Handle ping.
    socket.on('pongcheck', function () {
        var latency = Date.now() - global.startPingTime;
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

    // Handle connection.
    socket.on('welcome', function (playerSettings) {
        player = playerSettings;
        player.name = global.playerName;
        player.screenWidth = global.screenWidth;
        player.screenHeight = global.screenHeight;
        player.target = window.canvas.target;
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
    });

    socket.on('gameSetup', function(data) {
        global.gameWidth = data.gameWidth;
        global.gameHeight = data.gameHeight;
        resize();
    });

    socket.on('playerDied', function (data) {
        window.chat.addSystemLine('{GAME} - <b>' + (data.name.length < 1 ? 'An unnamed tank' : data.name) + '</b> was eaten.');
    });

    socket.on('playerDisconnect', function (data) {
        window.chat.addSystemLine('{GAME} - <b>' + (data.name.length < 1 ? 'An unnamed tank' : data.name) + '</b> disconnected.');
    });

    socket.on('playerJoin', function (data) {
        window.chat.addSystemLine('{GAME} - <b>' + (data.name.length < 1 ? 'An unnamed tank' : data.name) + '</b> joined.');
    });

    // socket.on('leaderboard', function (data) {
    //     leaderboard = data.leaderboard;
    //     var status = '<span class="title">Leaderboard</span>';
    //     for (var i = 0; i < leaderboard.length; i++) {
    //         status += '<br />';
    //         if (leaderboard[i].id == player.id){
    //             if(leaderboard[i].name.length !== 0)
    //                 status += '<span class="me">' + (i + 1) + '. ' + leaderboard[i].name + "</span>";
    //             else
    //                 status += '<span class="me">' + (i + 1) + ". An unnamed tank</span>";
    //         } else {
    //             if(leaderboard[i].name.length !== 0)
    //                 status += (i + 1) + '. ' + leaderboard[i].name;
    //             else
    //                 status += (i + 1) + '. An unnamed tank';
    //         }
    //     }
    //     //status += '<br />Players: ' + data.players;
    //     document.getElementById('status').innerHTML = status;
    // });

    socket.on('serverMSG', function (data) {
        window.chat.addSystemLine(data);
    });

    // Chat.
    socket.on('serverSendPlayerChat', function (data) {
        window.chat.addChatLine(data.sender, data.message, false);
    });

    socket.on('initial', function(data){
        console.log('initial', data)
        if (data.sprite === 'SpriteType.PLANET_SPRITE'){
            planets.push(data)
        } else if (data.sprite === 'SpriteType.GREY1_SPRITE'){
            console.log('pushing user', data.id)
            users.push(data)
        }
    });

    socket.on('update', function(data){
        //console.log('updating', data)
        if (data.sprite === 'SpriteType.PLANET_SPRITE'){
            //console.log(data)
            let planet;
            for (let j = 0; j < planets.length; j++){
                if (planets[j].id == data.id){
                    planet = planets[j];
                }
            }
            for (let i = 0; i < data.update.length; i++){
                let index = data.update[i][0];
                planet.altitudes[index] = data.update[i][1];
            }
        }

        else if (data.sprite == 'SpriteType.BULLET_SPRITE') {
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
            if (users[i].id == socket.id) {
                //console.log('found player')
                let health_inventory_changes = false;
                var xoffset = player.x - users[i].x;
                var yoffset = player.y - users[i].y;

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
        let explosions = explosionsList
    })
    // Handle movement.
    socket.on('-serverTellPlayerMove', function (data) {
        userData = data[0];
        foodsList = data[1];
        massList = data[2];
        virusList = data[3];
        var playerData;
        for(var i =0; i< userData.length; i++) {
            if(typeof(userData[i].id) == "undefined") {
                playerData = userData[i];
                i = userData.length;
            }
        }
        if(global.playerType == 'player') {
            var xoffset = player.x - playerData.x;
            var yoffset = player.y - playerData.y;

            player.x = playerData.x;
            player.y = playerData.y;
            player.hue = playerData.hue;
            //player.massTotal = playerData.massTotal;
            //player.cells = playerData.cells;
            player.xoffset = isNaN(xoffset) ? 0 : xoffset;
            player.yoffset = isNaN(yoffset) ? 0 : yoffset;

        }
        //users = userData;
        foods = foodsList;
        viruses = virusList;
        fireFood = massList;
    });

    // Death.
    socket.on('RIP', function () {
        global.gameStart = false;
        global.died = true;
        planets = []
        window.setTimeout(function() {
            document.getElementById('gameAreaWrapper').style.opacity = 0;
            document.getElementById('startMenuWrapper').style.maxHeight = '1000px';
            global.died = false;
            if (global.animLoopHandle) {
                window.cancelAnimationFrame(global.animLoopHandle);
                global.animLoopHandle = undefined;
            }
        }, 2500);
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
    })
}

function drawCircle(centerX, centerY, radius, sides) {
    var theta = 0;
    var x = 0;
    var y = 0;

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

function drawFood(food) {
    graph.strokeStyle = 'hsl(' + food.hue + ', 100%, 45%)';
    graph.fillStyle = 'hsl(' + food.hue + ', 100%, 50%)';
    graph.lineWidth = foodConfig.border;
    drawCircle(food.x - player.x + global.screenWidth / 2,
               food.y - player.y + global.screenHeight / 2,
               food.radius, global.foodSides);
}

function rotateAndDrawImage(context, image, angleInRadians, positionX, positionY, axisX=0, axisY=0, imageWidth=1, imageHeight=1){
    context.save()
    context.translate( positionX , positionY);
    context.rotate( angleInRadians );
    context.translate(- image.width/2, - image.height/2)
    context.drawImage( image, -axisX, -axisY , imageWidth * image.width, imageHeight*image.height);
    context.restore()
}

function getCenterXAndY(object){
    return {x:object.x - player.x + global.screenWidth/2,
            y:object.y - player.y + global.screenHeight/2}
}

function drawExplosion(explosion){
    let centerX = explosion.x - player.x + global.screenWidth / 2 ;
    let centerY = explosion.y - player.y + global.screenHeight / 2 ;

    let spriteName = explosion.sprite.substring(11);

    drawCircle(centerX, centerY, explosion.radius, 16)

    rotateAndDrawImage(graph, sprites[spriteName], 0, centerX, centerY, 0, 0)
}

function drawTrajectory(trajectory){
    console.log('drawing traj')
    graph.strokeStyle = 'red';
    graph.beginPath();
    for (let i = 0; i < trajectory.length; i++){
        let center = getCenterXAndY({x:trajectory[i][0], y:trajectory[i][1]});
        let centerX = center.x;
        let centerY = center.y;
        //graph.fillRect(centerX, centerY,1, 1);
        graph.moveTo(centerX, centerY);
    }
    graph.closePath()
    graph.stroke()

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
    let selectedIndex = player.selected_bullet;
    graph.fillStyle = "#ffffffff";
    graph.textAlign = "left";
    graph.font = "24px Arial";
    //go through each available bullet for player
    for (let i=0; i < 5; i++){//only display 5 bullets at a time
        let bulletIndex = i + selectedIndex;
        // Make sure our index is within the range of available bullets
        if (bulletIndex >= player.bullet_counts.length)
            bulletIndex -= player.bullet_counts.length;

        //set sprite and draw on side of screen
        let sprite_name = player.bullet_sprites[bulletIndex].substring(11);
        let sprite = sprites[sprite_name];



        let angle = i===0 ? Math.PI/4 : 0
        rotateAndDrawImage(graph, sprite, angle, 50, global.screenHeight/3 - 30 + (i*50));

        //Draw Bullet counts
        if (bulletIndex === 0 || bulletIndex === 1)
            graph.fillText("Infinite", 100, global.screenHeight/3 - 30 + (i * 50));
        else
            graph.fillText(player.bullet_counts[bulletIndex], 100, global.screenHeight/3- 30 + (i * 50));

        if (i===0)
            graph.fillText("<-", 175, global.screenHeight/3 - 30 + (i * 50));
    }
}

function drawTank(tank){
    let centerX = tank.x - player.x + global.screenWidth / 2 ;
    let centerY = tank.y - player.y + global.screenHeight / 2 ;

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


}

function drawPlanet(planet){
    let centerX = planet.x - player.x + global.screenWidth / 2
    let centerY = planet.y - player.y + global.screenHeight / 2

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

    var theta = 0;
    var x = 0;
    var y = 0;

    graph.beginPath();



    for (var i = 0; i < planet.number_of_altitudes; i++) {
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
    //console.log('drawing bullet');
    let centerX = bullet.x - player.x + global.screenWidth / 2;
    let centerY = bullet.y - player.y + global.screenHeight / 2;
    let sprite_name = bullet.sprite.substring(11); //The string passed includes 'SpriteType.' before the name
    // console.log(sprite_name)
    // console.log(sprites[sprite_name], bullet.roll, centerX, centerY)
    rotateAndDrawImage(graph, sprites[sprite_name], bullet.roll, centerX, centerY,0,0)
}

function drawVirus(virus) {
    graph.strokeStyle = virus.stroke;
    graph.fillStyle = virus.fill;
    graph.lineWidth = virus.strokeWidth;
    drawCircle(virus.x - player.x + global.screenWidth / 2,
               virus.y - player.y + global.screenHeight / 2,
               virus.radius, global.virusSides);
}

function drawFireFood(mass) {
    graph.strokeStyle = 'hsl(' + mass.hue + ', 100%, 45%)';
    graph.fillStyle = 'hsl(' + mass.hue + ', 100%, 50%)';
    graph.lineWidth = playerConfig.border+10;
    drawCircle(mass.x - player.x + global.screenWidth / 2,
               mass.y - player.y + global.screenHeight / 2,
               mass.radius-5, 18 + (~~(mass.masa/5)));
}

function drawPlayers(order) {
    var start = {
        x: player.x - (global.screenWidth / 2),
        y: player.y - (global.screenHeight / 2)
    };

    for(var z=0; z<order.length; z++)
    {
        var userCurrent = users[order[z].nCell];
        var cellCurrent = users[order[z].nCell];

        var x=0;
        var y=0;

        var points = 30 + ~~(cellCurrent.mass/5);
        var increase = Math.PI * 2 / points;

        graph.strokeStyle = 'hsl(' + userCurrent.hue + ', 100%, 45%)';
        graph.fillStyle = 'hsl(' + userCurrent.hue + ', 100%, 50%)';
        graph.lineWidth = playerConfig.border;

        var xstore = [];
        var ystore = [];

        global.spin += 0.0;

        var circle = {
            x: cellCurrent.x - start.x,
            y: cellCurrent.y - start.y
        };

        for (var i = 0; i < points; i++) {

            x = cellCurrent.radius * Math.cos(global.spin) + circle.x;
            y = cellCurrent.radius * Math.sin(global.spin) + circle.y;
            if(typeof(userCurrent.id) == "undefined") {
                x = valueInRange(-userCurrent.x + global.screenWidth / 2,
                                 global.gameWidth - userCurrent.x + global.screenWidth / 2, x);
                y = valueInRange(-userCurrent.y + global.screenHeight / 2,
                                 global.gameHeight - userCurrent.y + global.screenHeight / 2, y);
            } else {
                x = valueInRange(-cellCurrent.x - player.x + global.screenWidth / 2 + (cellCurrent.radius/3),
                                 global.gameWidth - cellCurrent.x + global.gameWidth - player.x + global.screenWidth / 2 - (cellCurrent.radius/3), x);
                y = valueInRange(-cellCurrent.y - player.y + global.screenHeight / 2 + (cellCurrent.radius/3),
                                 global.gameHeight - cellCurrent.y + global.gameHeight - player.y + global.screenHeight / 2 - (cellCurrent.radius/3) , y);
            }
            global.spin += increase;
            xstore[i] = x;
            ystore[i] = y;
        }
        /*if (wiggle >= player.radius/ 3) inc = -1;
        *if (wiggle <= player.radius / -3) inc = +1;
        *wiggle += inc;
        */
        for (i = 0; i < points; ++i) {
            if (i === 0) {
                graph.beginPath();
                graph.moveTo(xstore[i], ystore[i]);
            } else if (i > 0 && i < points - 1) {
                graph.lineTo(xstore[i], ystore[i]);
            } else {
                graph.lineTo(xstore[i], ystore[i]);
                graph.lineTo(xstore[0], ystore[0]);
            }

        }
        graph.lineJoin = 'round';
        graph.lineCap = 'round';
        graph.fill();
        graph.stroke();
        var nameCell = "";
        if(typeof(userCurrent.id) == "undefined")
            nameCell = player.name;
        else
            nameCell = userCurrent.name;

        var fontSize = Math.max(cellCurrent.radius / 3, 12);
        graph.lineWidth = playerConfig.textBorderSize;
        graph.fillStyle = playerConfig.textColor;
        graph.strokeStyle = playerConfig.textBorder;
        graph.miterLimit = 1;
        graph.lineJoin = 'round';
        graph.textAlign = 'center';
        graph.textBaseline = 'middle';
        graph.font = 'bold ' + fontSize + 'px sans-serif';

        if (global.toggleMassState === 0) {
            graph.strokeText(nameCell, circle.x, circle.y);
            graph.fillText(nameCell, circle.x, circle.y);
        } else {
            graph.strokeText(nameCell, circle.x, circle.y);
            graph.fillText(nameCell, circle.x, circle.y);
            graph.font = 'bold ' + Math.max(fontSize / 3 * 2, 10) + 'px sans-serif';
            if(nameCell.length === 0) fontSize = 0;
            graph.strokeText(Math.round(cellCurrent.mass), circle.x, circle.y+fontSize);
            graph.fillText(Math.round(cellCurrent.mass), circle.x, circle.y+fontSize);
        }
    }
}

function valueInRange(min, max, value) {
    return Math.min(max, Math.max(min, value));
}

function drawgrid() {
     graph.lineWidth = 1;
     graph.strokeStyle = global.lineColor;
     graph.globalAlpha = 0.15;
     graph.beginPath();

    for (var x = global.xoffset - player.x; x < global.screenWidth; x += global.screenHeight / 18) {
        graph.moveTo(x, 0);
        graph.lineTo(x, global.screenHeight);
    }

    for (var y = global.yoffset - player.y ; y < global.screenHeight; y += global.screenHeight / 18) {
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
        graph.fillStyle = '#333333';
        graph.fillRect(0, 0, global.screenWidth, global.screenHeight);

        graph.textAlign = 'center';
        graph.fillStyle = '#FFFFFF';
        graph.font = 'bold 30px sans-serif';
        graph.fillText('You died!', global.screenWidth / 2, global.screenHeight / 2);
    }
    else if (!global.disconnected) {
        if (global.gameStart) {
            graph.clearRect(0, 0, global.screenWidth, global.screenHeight);
            planets.forEach(drawPlanet)
            users.forEach(drawTank);
            bullets.forEach(drawBullet);
            explosions.forEach(drawExplosion);
            //drawHPBar(player.health)
            drawInventory();
            //drawTrajectory(trajectory);

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

    player.screenWidth = c.width = global.screenWidth = global.playerType === 'player' ? window.innerWidth : global.gameWidth;
    player.screenHeight = c.height = global.screenHeight = global.playerType === 'player' ? window.innerHeight : global.gameHeight;

    if (global.playerType === 'spectate') {
        player.x = global.gameWidth / 2;
        player.y = global.gameHeight / 2;
    }

    socket.emit('windowResized', { screenWidth: global.screenWidth, screenHeight: global.screenHeight });
}
