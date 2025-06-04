<?php
session_start();

// Connessione al database
$conn = mysqli_connect("localhost", "root", "", "piattaforma_streaming_musicale");

// Query per recuperare i brani
$sql_brani = "SELECT * FROM contenuto JOIN crea_contenuto WHERE contenuto.idContenuto=crea_contenuto.idContenuto AND tipo = 0";
$result_brani = mysqli_query($conn, $sql_brani);

// Query per recuperare i podcast
$sql_podcast = "SELECT * FROM contenuto JOIN crea_contenuto WHERE contenuto.idContenuto=crea_contenuto.idContenuto AND tipo = 1";
$result_podcast = mysqli_query($conn, $sql_podcast);

// Query per recuperare le playlist dell'utente loggato
$email=$_SESSION['email'];
$user_id = $_SESSION['user_id'];
?>

<!DOCTYPE html>
<html>
<head>
	<meta charset="UTF-8">
	<title>Streaming Musicale - Home home_free</title>
	<link rel="stylesheet" type="text/css" href="style.css">
</head>
<body>
	<div class="container">
		<h1>Streaming Musicale - Home Free</h1>
		<p>Benvenuto <?php echo $_SESSION['email']; ?>. Qui di seguito trovi alcuni dei nostri brani in vetrina:</p>
		<table>
		<tr>
			<th>Titolo</th>
			<th>Artista</th>
			<th>Durata</th>
		</tr>
		<?php
			// Mostra i brani
			while($row = mysqli_fetch_assoc($result_brani)){
			echo "<tr>";
			echo "<td>" . $row['nome'] . "</td>";
			echo "<td>" . $row['nomeArtista'] . "</td>";
			echo "<td>" . $row['duarata'] . "</td>";
			echo "</tr>";
			}
		?>
		</table>
		<p>Non dimenticare di dare un'occhiata anche ai nostri podcast!</p>
		<table>
		<tr>
			<th>Titolo</th>
			<th>Artista</th>
			<th>Durata</th>
		</tr>
		<?php
			// Mostra i brani
			while($row = mysqli_fetch_assoc($result_podcast)){
			echo "<tr>";
			echo "<td>" . $row['nome'] . "</td>";
			echo "<td>" . $row['nomeArtista'] . "</td>";
			echo "<td>" . $row['duarata'] . "</td>";
			echo "</tr>";
			}
		?>
		</table>
	</div>
</body>
</html>
