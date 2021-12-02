window.onscroll = function() {myFunction()};

var header = document.getElementById("myHeader");
var sticky = header.offsetTop;

function myFunction() {
  if (window.pageYOffset > sticky) {
    header.classList.add("sticky");
  } else {
    header.classList.remove("sticky");
  }
}

//var sel = document.getElementById('months_select');
//sel.onchange = function () {
function monthSelect() {
    var x = document.getElementById("months_select").value;
    //document.getElementById("months_select_button").href = "#" + this.value;
    //document.getElementById("months_select_button").onclick = x;
    document.getElementById("months_select_button").value = location.href=x;;  // Somehow this triggers page to load lol
}
