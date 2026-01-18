// === Firebase INIT (v8) === //

var firebaseConfig = {
    apiKey: "AIzaSyDkQTqt1Hcg7H-a4rVl88dCbdJkDEiPDEg",
    authDomain: "codebug-47347.firebaseapp.com",
    databaseURL: "https://codebug-47347-default-rtdb.europe-west1.firebasedatabase.app",
    projectId: "codebug-47347",
    storageBucket: "codebug-47347.appspot.com",
    messagingSenderId: "1000157426060",
    appId: "1:1000157426060:web:4350f2d9f3db75e407e6a9"
};

// Чтобы firebase был доступен
console.log("firebase =", window.firebase);

// Инициализация (v8 — ТОЛЬКО ТАК!)
firebase.initializeApp(firebaseConfig);

// Глобальная переменная DB
window.db = firebase.database();
window.firebase = firebase;
window.TASKS_API_BASE = window.TASKS_API_BASE || (
    location.hostname === "localhost" ? "http://localhost:7777" : "https://codebug.onrender.com"
);

console.log("Firebase INIT OK, db =", window.db);
