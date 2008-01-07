#!/usr/bin/perl

use strict;
use warnings;

use CGI::Carp qw(fatalsToBrowser);
use CGI::Simple;
use DBI;
use Template;
use String::Random;
use DateTime;
use DateTime::Format::Strptime;
use DateTime::Format::MySQL;

# Script name and path
my $script_base = "http://www.mysite.com/cgi-bin/adm/index.cgi";

# Database configuration
my $database_name      = 'radius';
my $database_host      = 'localhost';
my $database_port      = 3306;
my $database_user      = 'freeradius';
my $database_password  = 'pwd';

our $VERSION = '0.02004';

# Create query object
my $q = new CGI::Simple;

# Connect to MySQL database
my $dbh = DBI->connect(
	"DBI:mysql:$database_name:$database_host:$database_port"
	, $database_user
	, $database_password
	);
die q{1: (can\'t connect to SQL server)} if !$dbh;

my $t = new Template( {
	INCLUDE_PATH 	=> './t',
	DEBUG		=> 1,
} );

# Dispatcher
TASKS:
{
	if ($q->param('task') eq 'ecreate') { ecreate(); last TASKS; }
	if ($q->param('task') eq 'ddisable') { ddisable(); last TASKS; }
	print $q->header(-charset => 'UTF-8');
	if ($q->param('task') eq 'eview') { eview(); last TASKS; }
	if ($q->param('task') eq 'elist') { elist(); last TASKS; }
	emain();
};

#######################################################################
# Purpose: show main page where to create a login
sub emain {
	my $t_file = 'emain.tt';

	my $dtf_strp = DateTime::Format::Strptime->new(
		pattern	=> '%Y-%m-%d %H:%M:%S',
	);

	my $now = DateTime->now( time_zone => 'local');
	$t->process( $t_file, {
		starttime	=> $dtf_strp->format_datetime($now),
	} );
}

#######################################################################
# Purpose: create a login
sub ecreate {
	my $t_file = 'ecreate.tt';

	my $dtf_strp = DateTime::Format::Strptime->new(
		pattern	=> '%Y-%m-%d %H:%M:%S',
	);

	# Create a new start date
	my $starttime = $dtf_strp->parse_datetime(
		$q->param('starttime')
	);
	die "Invalid-starttime" if !defined $starttime;
	$starttime->time_zone('local');
	
	# Die away if hour is not numeric
	my $hours = $q->param('hours');
	die 'ecreate-0: invalid hours value' if $hours !~ m/\A \d+ \z/x;
	$hours = sprintf "%02d", $hours;

	# Calculate endtime: easy ;-)
	my $endtime = $starttime + DateTime::Duration->new(
		hours	=> $hours
	);
	
	# Get a new username and password
	my $string_generator = String::Random->new;
	my $UserName = $string_generator->randpattern('cccccc');
	my $Value = $string_generator->randpattern('nnnnn');

	# Begin transaction
	$dbh->begin_work();
	
	# Insert username and password into database
	$dbh->do("
		insert into radcheck (
		UserName, Attribute, op, Value
		) values (
		'$UserName', 'Password', '==', '$Value'
		)
	") or die "ecreate-1: ".$dbh->errstr();

	# Escape data before insertion
	my $name = $dbh->quote( $q->param('name') );
	my $room = $dbh->quote( $q->param('room') );

	my $starttime_sql
		= DateTime::Format::MySQL->format_datetime($starttime);
	my $endtime_sql
		= DateTime::Format::MySQL->format_datetime($endtime);

	# Insert user details
	$dbh->do("
		insert into mb_user_details (
		UserName, activated, expires,
		name, room
		) values (
		'$UserName',
		'$starttime_sql', '$endtime_sql',
		$name, $room
		)
	") or die "ecreate-2: ".$dbh->errstr();
	
	my $id = $dbh->{mysql_insertid};

	# Commit transaction
	$dbh->commit();

	print $q->header(
		-location => "$script_base?task=eview&id=$id"
	);
}

#######################################################################
# Purpose: view a created login
sub eview {
	my $t_file = 'eview.tt';

	# Die away if ID is not numeric
	my $id = $q->param('id');
	die 'eview-0: invalid ID' if $id !~ m/\A \d+ \z/x;
	
	# Get data of login
	my $login_ref = $dbh->selectrow_hashref("
		select mb_user_details.id, mb_user_details.UserName,
		unix_timestamp(mb_user_details.activated) as activated,
		unix_timestamp(mb_user_details.expires) as expires,
		mb_user_details.name, mb_user_details.room,
		radcheck.id as radiusid, radcheck.Value as UserPassword
		from mb_user_details
		left join radcheck on radcheck.UserName = mb_user_details.UserName
		where mb_user_details.id = $id
	") or die "eview-1: ".$dbh->errstr();

	$t->process( $t_file,  { login_data => $login_ref } );
}

#######################################################################
# Purpose: list created logins
sub elist {
	my $t_file = 'elist.tt';

	# If we have no date, show current month
	use POSIX;
	my @ltime = localtime();
	my $month = strftime("%m", @ltime);
	my $year  = strftime("%Y", @ltime);
	
	# Get data of login
	my $query = "
		select mb_user_details.id, mb_user_details.UserName,
		unix_timestamp(mb_user_details.activated) as activated,
		unix_timestamp(mb_user_details.expires) as expires,
		mb_user_details.name, mb_user_details.room,
		radcheck.id as radiusid, radcheck.Value as UserPassword
		from mb_user_details
		left join radcheck
		  on radcheck.UserName = mb_user_details.UserName
		where
		year(mb_user_details.activated) = $year
		and month(mb_user_details.activated) = $month
	";
	my $sth = $dbh->prepare( $query )
		or die "elist-1: ".$dbh->errstr();
	$sth->execute() or die "elist-1: ".$dbh->errstr();
	my $logins_ref = $sth->fetchall_arrayref( {} );

	$t->process( $t_file,  {
		logins => $logins_ref,
		month  => $month,
		year   => $year,
	} );
}

#######################################################################
# Purpose: disable a login
sub ddisable {
	# Die away if ID is not numeric
	my $id = $q->param('id');
	die 'ddisable-0: invalid ID' if $id !~ m/\A \d+ \z/x;

	# Get expired users
	my $expired_user_ref = $dbh->selectrow_hashref("
		select UserName
		from mb_user_details
		where id = $id
	") or die 'ddisable-1: '.$dbh->errstr();
                         
	# Begin transaction
	$dbh->begin_work();

	# Delete entry from radcheck table
        $dbh->do("
		delete from
		radcheck
		where UserName = '$expired_user_ref->{UserName}'
	") or die 'ddisable-2: '.$dbh->errstr();
	
	# Update expiration to now
        $dbh->do("
		update
		mb_user_details
		set expires = now()
		where id = $id
	") or die 'ddisable-2: '.$dbh->errstr();

	# Commit transaction
	$dbh->commit();			
	
	print $q->header(
		-location => $ENV{HTTP_REFERER}
	);
}
