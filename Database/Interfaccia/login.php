<!DOCTYPE html>
<html>
<head>
	<meta charset="UTF-8">
	<title>Login</title>
	<link rel="stylesheet" type="text/css" href="style.css">
</head>
<body>
	<div class="container">
		<h1>Login</h1>
		<form method="post" action="login.php">
			<label for="email">Email</label>
			<input type="text" id="email" name="email" required>
			<label for="password">Password</label>
			<input type="password" id="password" name="password" required>
			<input type="submit" value="Login">
		</form>
		<?php
			if(isset($_GET['error'])){
				echo "<p class='error'>Email o password non validi.</p>";
			}
		?>
	</div>
</body>
</html>

<?php
session_start();

// Connessione al database
$host = "localhost";
$username = "root";
$password = "";
$dbname = "piattaforma_streaming_musicale";

$conn = mysqli_connect($host, $username, $password, $dbname);

if(mysqli_connect_errno()){
    echo "Errore di connessione al database: ".mysqli_connect_error();
    exit();
}

// Controllo se l'utente ha fatto il login
if(isset($_POST['email']) && isset($_POST['password'])){
    $email = $_POST['email'];
    $password_input = $_POST['password'];

    // Query per recuperare l'utente dal database
$query = "SELECT * FROM utente WHERE email='$email'";

$result = mysqli_query($conn, $query);

if(mysqli_num_rows($result) == 1){
    // L'utente è stato trovato nel database
    $row = mysqli_fetch_assoc($result);

    if(($password_input==$row['passw'])){
    // Password corretta, l'utente viene loggato
    $_SESSION['user_id'] = $row['id'];
    $_SESSION['email'] = $row['email'];

        // Controllo il tipo di utente e reindirizzo alla pagina corretta
        if($row['tipo'] == 1){
            header("Location: home_premium.php");
            exit();
        }else if($row['tipo'] == 0){
            header("Location: home_free.php");
            exit();
        }
    }
}

// Se l'utente non è stato trovato o la password è sbagliata, mostro un errore
header("Location: login.php?error=true");
exit();

}
?>

