// === Firebase INIT (v8) === //

var firebaseConfig = {
    apiKey: "AIzaSyDkQTqt1Hcg7H-a4rVl88dCbdJkDEiPDEg",
    authDomain: "codebug-47347.firebaseapp.com",
    databaseURL: "https://codebug-47347-default-rtdb.europe-west1.firebasedatabase.app",
    projectId: "codebug-47347",
    storageBucket: "codebug-47347.appspot.com", // ← исправлено !!!
    messagingSenderId: "1000157426060",
    appId: "1:1000157426060:web:4350f2d9f3db75e407e6a9"
};

// Инициализация
firebase.initializeApp(firebaseConfig);

// ГЛОБАЛЬНАЯ переменная
window.db = firebase.database();