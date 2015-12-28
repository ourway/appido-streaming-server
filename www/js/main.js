
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
                    controller: 'VideoPlayerController'
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
app.controller('VideoPlayerController', function($scope, $http, $routeParams, $interval){

            
           var ticket_id = $routeParams.ticket_id;
           var url = "/static/videos/"+ ticket_id +"/rashavas.mpd";
           console.log(url);

           var context = new Dash.di.DashContext();

           var player = new MediaPlayer(context);

           player.startup();

           player.attachView(document.querySelector("#videoPlayer"));

           player.attachSource(url);


})
