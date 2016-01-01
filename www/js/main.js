
'use strict';

var app = angular.module('ngApp', ['ngRoute', 'flow']);

app.config(['$routeProvider',
        function($routeProvider) {
            $routeProvider.
                when('/', {
                    templateUrl: 'templates/home.html',
                    controller: 'HomeController'
            })
                .when('/upload', {
                    templateUrl: 'templates/upload/index.html',
            })
                .when('/upload/video', {
                    templateUrl: 'templates/upload/video.html',
                    controller: 'VideoUploadController'
            })
                .when('/upload/audio', {
                    templateUrl: 'templates/upload/audio.html',
                    controller: 'AudioUploadController'
            })
 
                .when('/status/convert/:ticket_id', {
                    templateUrl: 'templates/status/convert.html',
                    controller: 'ConvertStatusController'
            })
                .when('/play/video/:ticket_id', {
                    templateUrl: 'templates/play/video.html',
                    controller: 'DashVideoPlayerController'
            })
                .when('/play/video-dash', {
                    templateUrl: 'templates/play/video.html',
                    controller: 'DashVideoPlayerController'
            })

                .when('/play/video-hls', {
                    templateUrl: 'templates/play/video.html',
                    controller: 'HLSVideoPlayerController'
 

            })
 

    }]);


app.controller('MainController', function($scope, $http, $rootScope){

    $scope.getReadableFileSizeString = getReadableFileSizeString;
    $scope.parseMessage = function(message){
        var data = JSON.parse(message)
        return data;
    };
    $scope.parseInt = parseInt;


});
app.controller('HomeController', function($scope, $http, $rootScope){});
app.controller('VideoUploadController', function($scope, $http, $rootScope){

});
app.controller('AudioUploadController', function($scope, $http, $rootScope){});
app.controller('ConvertStatusController', function($scope, $http, $routeParams, $interval){

        var ticket_id = $routeParams.ticket_id;
        $scope.getStatus = function(){
            var req = $http.get('/api/key/'+ticket_id);
            req.then(function(resp){
                $scope.status = resp.data;

            });

        };

        $scope.getStatus();
        $interval($scope.getStatus, 1000);

});
app.controller('DashVideoPlayerController', function($scope, $http, $routeParams, $interval){

            
    var ticket_id = $routeParams.ticket_id;

   
    $scope.playDash = function(url){
        shaka.polyfill.installAll();
        var video = document.getElementById('videoPlayer');
        var player = new shaka.player.Player(video);
        window.player = player;
              player.addEventListener('error', function(event) {
                console.error(event);
              });
        var estimator = new shaka.util.EWMABandwidthEstimator();
        var source = new shaka.player.DashVideoSource(url, null, estimator);
        player.load(source);
    }


    $scope.play = function(url){
        console.log(url);
        if (url.indexOf('.mpd')>-1){
        $scope.playDash(url);
        // videojs("videoPlayer", {}, function(){
        //});


        }
        else{
            alert('I can only play dash')
        }
    }

    if (ticket_id)
        {
            var url = "/static/videos/"+ ticket_id +"/rashavas.mpd";
            $scope.play(url);
        }
 

});




app.controller('HLSVideoPlayerController', function($scope, $http, $routeParams, $interval){

    $scope.playHLS = function(url){

        var video = document.getElementById('videoPlayer');
        var hls = new Hls();
        hls.loadSource(url);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED,function() {
            video.play();
        });
    }


    $scope.play = function(url){
        if (url.indexOf('m3u8')>-1){
            videojs.players = {};
            $scope.playHLS(url);
        }
        else{
            alert('I can only play hls')
        }
    }


});



