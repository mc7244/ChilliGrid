#!/usr/bin/perl

use strict;
use warnings;

use DBI;

# Database configuration
my $database_name      = 'radius';
my $database_host      = 'localhost';
my $database_port      = 3306;
my $database_user      = 'freeradius';
my $database_password  = 'pwd';
my $radius_secret      = 'secret';

our $VERSION = '0.01003';

# Connect to MySQL database
my $dbh = DBI->connect(
	"DBI:mysql:$database_name:$database_host:$database_port"
	, $database_user
	, $database_password
);
die q{1: (can\'t connect to SQL server)} if !$dbh;

# Get expired users
my $expired_users_ref = $dbh->selectcol_arrayref("
	select UserName
	from mb_user_details
	where expires <= now()
    and deleted = 0
") or die 'main-1: '.$dbh->errstr();

# Delete expired users
for my $expired_user ( @$expired_users_ref ) {
    $dbh->do("delete from
        radcheck
        where UserName = ?
    ", undef, $expired_user) or die $dbh->errstr;

    # Logoff any user which is still connected, otherwise he'll be
    # able to use the service until he logs off
    system("/usr/bin/echo \"User-Name=$expired_user\" | /usr/bin/radclient -x 127.0.0.1:3799 disconnect $radius_secret"); 

    # Update user details table
    $dbh->do("update
        mb_user_details
        set deleted = 1
        where UserName = ?
    ", undef, $expired_user) or die $dbh->errstr;
}

